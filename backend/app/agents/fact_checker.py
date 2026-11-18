"""Evidence-based factual claim extraction and verification."""

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent


VerificationStatus = Literal[
    "supported", "contradicted", "insufficient_evidence"
]


class ClaimExtraction(BaseModel):
    claims: list[str] = Field(default_factory=list, max_length=50)


class ClaimVerification(BaseModel):
    verification_status: VerificationStatus
    explanation: str = Field(min_length=1, max_length=4000)
    confidence_score: float = Field(ge=0, le=1)
    evidence_references: list[str] = Field(default_factory=list, max_length=20)


class FactCheckerAgent(BaseAgent):
    """Verify claims only against supplied, traceable evidence."""

    def __init__(self, llm=None, retrieval=None, *, user_id=None):
        super().__init__(name="Fact Checker")
        self.llm = llm
        self.retrieval = retrieval
        self.user_id = user_id

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        claims = [str(claim) for claim in state.get("extracted_claims", []) if str(claim).strip()]
        evidence = self._state_evidence(state)
        provider = self.llm or self._get_llm()
        errors = []
        if not claims and not evidence:
            state["extracted_claims"] = []
            state["verified_claims"] = []
            state["fact_check_status"] = "no_results"
            state["current_step"] = "fact_checking_completed"
            state["agents_completed"] = state.get("agents_completed", []) + ["fact_checker"]
            return state
        if not claims:
            try:
                extracted = await provider.generate_structured(
                    (
                        "Extract individual factual claims from the supplied "
                        "research evidence. Do not invent claims; return an empty "
                        "list when there are no factual claims.\n\n"
                        f"Evidence:\n{json.dumps(evidence, ensure_ascii=True)[:24000]}"
                    ),
                    ClaimExtraction,
                )
                claims = extracted.claims
            except Exception as exc:
                errors.append(str(exc))
        verified = []
        for claim in claims:
            if self.retrieval is not None and self.user_id is not None:
                try:
                    retrieved = self.retrieval.retrieve(
                        claim,
                        user_id=self.user_id,
                        document_ids=state.get("document_ids") or None,
                        top_k=5,
                    )
                    evidence.extend(
                        {
                            "reference": record["citation"],
                            "text": record["content"][:6000],
                        }
                        for record in self.retrieval.construct_context_records(retrieved)
                    )
                except Exception as exc:
                    errors.append(str(exc))
            result = await self._verify_claim(claim, evidence, provider)
            if result.get("error"):
                errors.append(result["error"])
            verified.append(result)
        state["extracted_claims"] = claims
        state["verified_claims"] = verified
        state["fact_check_status"] = "failed" if errors else "completed"
        if errors:
            state.setdefault("research_errors", {})["Fact Checker"] = "; ".join(errors)
        state["current_step"] = "fact_checking_completed"
        state["agents_completed"] = state.get("agents_completed", []) + ["fact_checker"]
        return state

    async def _verify_claim(
        self, claim: str, evidence: list[dict[str, Any]], provider
    ) -> dict[str, Any]:
        relevant = self._relevant_evidence(claim, evidence)
        base = {
            "claim_text": claim,
            "verification_status": "insufficient_evidence",
            "explanation": "No relevant evidence was available for this claim.",
            "confidence_score": 0.0,
            "evidence": None,
            "evidence_references": [],
        }
        if not relevant:
            return base
        try:
            evaluation = await provider.generate_structured(
                (
                    "Evaluate the claim only against the supplied evidence. "
                    "Use supported or contradicted only when the evidence directly "
                    "supports that status; otherwise use insufficient_evidence. "
                    f"\n\nClaim: {claim}\nEvidence:\n{json.dumps(relevant, ensure_ascii=True)}"
                ),
                ClaimVerification,
            )
        except Exception as exc:
            return {**base, "error": str(exc)}
        references = [
            reference for reference in evaluation.evidence_references
            if reference in {item["reference"] for item in relevant}
        ]
        if evaluation.verification_status != "insufficient_evidence" and not references:
            return {
                **base,
                "explanation": "The model did not attribute a supporting evidence reference.",
            }
        status = evaluation.verification_status
        return {
            **base,
            "verification_status": status,
            "explanation": evaluation.explanation,
            "confidence_score": evaluation.confidence_score if status != "insufficient_evidence" else 0.0,
            "evidence": "; ".join(references) if references else None,
            "evidence_references": references,
        }

    def _state_evidence(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        evidence = []
        for index, source in enumerate(state.get("research_sources", []), start=1):
            text = " ".join(
                str(source.get(key) or "")
                for key in ("title", "summary", "content", "abstract")
            ).strip()
            if text:
                evidence.append({
                    "reference": str(source.get("url") or source.get("title") or f"source-{index}"),
                    "text": text[:6000],
                })
        for finding in state.get("document_findings", []):
            for passage in finding.get("relevant_passages", []):
                evidence.append({
                    "reference": passage.get("citation") or passage.get("chunk_id"),
                    "text": passage.get("content", "")[:6000],
                })
        return [item for item in evidence if item["reference"] and item["text"]]

    @staticmethod
    def _relevant_evidence(claim: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        terms = {term.lower() for term in claim.split() if len(term) > 3}
        return [
            item for item in evidence
            if any(term in item["text"].lower() for term in terms)
        ][:8]
