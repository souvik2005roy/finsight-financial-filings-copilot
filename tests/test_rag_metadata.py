import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import rag


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakePdfReader:
    def __init__(self, _path):
        self.pages = [
            FakePage("The supply chain depends on component suppliers."),
            FakePage("Operating margin was 18.4 percent."),
        ]


def test_retriever_preserves_pdf_page_numbers(tmp_path, monkeypatch):
    pdf_path = tmp_path / "example.pdf"
    pdf_path.write_bytes(b"fake pdf; reader is monkeypatched")
    monkeypatch.setattr(rag, "PdfReader", FakePdfReader)

    retriever = rag.Retriever(str(tmp_path))

    assert retriever.pages == [1, 2]
    assert retriever.citation_for(0) == "[example.pdf, PDF page 1]"
    assert retriever.citation_for(1) == "[example.pdf, PDF page 2]"
    assert retriever.chunk_ids[0].startswith("example.pdf:p0001:")


def test_rag_prompt_has_citation_but_checker_evidence_does_not(tmp_path, monkeypatch):
    pdf_path = tmp_path / "example.pdf"
    pdf_path.write_bytes(b"fake pdf; reader is monkeypatched")
    monkeypatch.setattr(rag, "PdfReader", FakePdfReader)
    retriever = rag.Retriever(str(tmp_path))
    monkeypatch.setattr(retriever, "search", lambda _q, _k, _mode, **kwargs: [1])

    captured = {}

    def fake_ask_llm(prompt):
        captured["prompt"] = prompt
        return "Operating margin was 18.4 percent [example.pdf, PDF page 2]."

    monkeypatch.setattr(rag, "ask_llm", fake_ask_llm)
    answer, sources, evidence = rag.rag_answer("What was operating margin?", retriever)

    assert "[example.pdf, PDF page 2]" in captured["prompt"]
    assert "18.4" in evidence
    assert "PDF page 2" not in evidence
    assert sources == ["[example.pdf, PDF page 2]"]
    assert "18.4" in answer

