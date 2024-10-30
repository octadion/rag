from langchain.prompts import PromptTemplate

PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Answer the question based on the above context and previous question: {question}
"""

prompt = PromptTemplate.from_template(
    """Analisa teks percakapan berikut ke dalam format di bawah serta klasifikasikanlah ke dalam salah satu label:

    Konteks Percakapan: 
    {{konteks_percakapan}}

    Keyword Extraction: 
    {{keyword_extraction}}

    Intent Recognition: 
    {{intent_recognition}}

    Kualifikasi Lead: 
    {{kualifikasi_lead}}

    Label: [L1-Qualified, S_JUNK, Qualified, L1-Junk]

    {input}
    """
)