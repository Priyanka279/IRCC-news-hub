import os
from dotenv import load_dotenv
load_dotenv()

def get_ai_summary(title: str, raw_summary: str) -> str:
    """Get AI-powered plain English summary using Groq (free)."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return raw_summary  # fallback to original if no key
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{
                "role": "user",
                "content": f"""Summarize this Canadian immigration news in 1-2 plain English sentences.
Be specific about numbers (CRS scores, dates, quotas) if mentioned.
Title: {title}
Content: {raw_summary}
Summary:"""
            }],
            max_tokens=100,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ai] Summary failed: {e}")
        return raw_summary