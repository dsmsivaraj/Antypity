from typing import Optional, Dict, Any

from shared.base_agent import BaseAgent, AgentResult, AgentMetadata


class LlamaResumeAgent(BaseAgent):
    """Agent that understands and summarizes resumes using a local LLaMA model if available.
    Falls back to the configured LLMClient when local model isn't installed.
    """

    def __init__(self, llm_client=None, skills=None):
        meta = AgentMetadata(
            name="LlamaResumeAgent",
            description="Process and summarize resumes; provide resume-aware chat",
            capabilities={"resume:process", "resume:chat"},
            supports_tools=False,
        )
        super().__init__(metadata=meta)
        self.llm_client = llm_client
        self.skills = skills

    def can_handle(self, task: str, context: Optional[Dict[str, Any]] = None) -> int:
        low = task.lower() if task else ""
        if any(k in low for k in ("resume", "cv", "curriculum vitae", "cover letter", "jd", "job description")):
            return 90
        return 0

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None):
        # context may include 'resume_text' and/or 'jd_text'
        resume_text = None
        if context:
            resume_text = context.get("resume_text") or context.get("text")
        prompt = f"You are a resume assistant. Task: {task}\nResume:\n{(resume_text or '')[:6000]}"

        # Try local LLaMA client first
        try:
            from backend.llama_client import LlamaClient

            client = LlamaClient()
            out = client.generate(prompt, max_tokens=256)
            return AgentResult(output=out, used_llm=True, metadata={})
        except Exception:
            # Fallback to configured LLM client if available
            if self.llm_client:
                try:
                    # LLMClient.complete may return an object; adapt accordingly
                    res = self.llm_client.complete(prompt)
                    text = getattr(res, "output", None) or str(res)
                    return AgentResult(output=text, used_llm=True, metadata={})
                except Exception:
                    return AgentResult(output="LLM invocation failed.", used_llm=False, metadata={})

        return AgentResult(output="No LLM available to process this resume.", used_llm=False, metadata={})
