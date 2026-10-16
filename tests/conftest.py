import pytest


@pytest.fixture(autouse=True)
def isolated_output(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ('GOOGLE_API_KEY','GEMINI_API_KEY','GEMINI_MODEL','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GENAI_USE_ENTERPRISE'):
        monkeypatch.delenv(name,raising=False)
