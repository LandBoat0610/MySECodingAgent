"""RAG 模块单元测试。"""
import json
import os
import tempfile

import pytest

# conftest.py 已设置环境变量和 sys.path


# ── 文档加载与切分 ────────────────────────────────────
class TestDocumentLoading:
    def test_load_markdown(self, tmp_path):
        from agent.backend.rag import load_markdown
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n\nWorld", encoding="utf-8")
        text = load_markdown(str(md_file))
        assert "Hello" in text
        assert "World" in text

    def test_load_file_txt(self, tmp_path):
        from agent.backend.rag import load_file
        txt_file = tmp_path / "note.txt"
        txt_file.write_text("some content", encoding="utf-8")
        text = load_file(str(txt_file))
        assert text == "some content"

    def test_load_file_nonexistent(self):
        from agent.backend.rag import load_markdown

        with pytest.raises(FileNotFoundError):
            load_markdown("/nonexistent/path/file.md")


class TestSplitChunks:
    def test_basic_split(self):
        from agent.backend.rag import split_chunks
        text = "段落一\n\n段落二\n\n段落三"
        chunks = split_chunks(text, source="test.md", chunk_size=100)
        assert len(chunks) >= 1
        for c in chunks:
            assert "content" in c
            assert "source" in c
            assert c["source"] == "test.md"

    def test_long_paragraph_split(self):
        from agent.backend.rag import split_chunks
        text = "A" * 1200  # 超过默认 chunk_size
        chunks = split_chunks(text, source="long.txt", chunk_size=500)
        assert len(chunks) > 1
        # 每个 chunk 的 content 不超过 chunk_size + 一点 overlap
        for c in chunks:
            assert len(c["content"]) <= 500 + 50

    def test_empty_text(self):
        from agent.backend.rag import split_chunks
        chunks = split_chunks("", source="empty.md")
        assert chunks == []

    def test_chunk_has_index(self):
        from agent.backend.rag import split_chunks
        text = "AAA\n\nBBB\n\nCCC"
        chunks = split_chunks(text, source="idx.md", chunk_size=100)
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i


# ── Chroma 集成（使用临时目录避免污染） ───────────────
class TestChromaIntegration:
    @pytest.fixture(autouse=True)
    def reset_rag_globals(self, tmp_path, monkeypatch):
        """每个测试用临时目录作为 RAG 存储，并重置全局客户端。"""
        import agent.backend.rag as rag_mod
        monkeypatch.setattr(rag_mod, "_chroma_client", None)
        monkeypatch.setattr(rag_mod, "_collection", None)
        monkeypatch.setattr(rag_mod, "RAG_STORE_DIR", str(tmp_path / "rag_store"))

    def test_ingest_and_search(self, tmp_path, monkeypatch):
        """端到端测试：入库 → 检索（mock embedding）。"""
        from agent.backend.rag import ingest_documents, rag_search

        # 创建测试文档
        doc = tmp_path / "test_doc.md"
        doc.write_text(
            "迭代三需要完成 RAG 知识增强模块。"
            "RAG 模块包括文档加载、切分、向量化和检索功能。"
            "Agent 可以通过 rag_search 工具查询知识库。",
            encoding="utf-8",
        )

        # Mock embedding 函数，返回固定维度的随机向量
        import agent.backend.rag as rag_mod
        import numpy as np

        call_count = {"n": 0}

        def mock_embed(texts):
            call_count["n"] += 1
            return [np.random.rand(1024).tolist() for _ in texts]

        monkeypatch.setattr(rag_mod, "_embed_texts", mock_embed)

        # 入库
        result = ingest_documents([str(doc)])
        assert result["status"] == "success"
        assert result["chunks_added"] > 0

        # 检索
        search_result = rag_search("RAG 知识增强", top_k=3)
        assert search_result["query"] == "RAG 知识增强"
        assert len(search_result["results"]) > 0
        for r in search_result["results"]:
            assert "content" in r
            assert "source" in r
            assert "score" in r

    def test_search_empty_store(self, monkeypatch):
        """空知识库搜索应返回空结果。"""
        from agent.backend.rag import rag_search
        result = rag_search("something")
        assert result["results"] == []

    def test_ingest_nonexistent_file(self, monkeypatch):
        """入库不存在的文件应跳过。"""
        from agent.backend.rag import ingest_documents
        result = ingest_documents(["/nonexistent/file.md"])
        assert result["status"] == "error"

    def test_get_rag_stats(self, tmp_path, monkeypatch):
        """统计信息应正常返回。"""
        from agent.backend.rag import get_rag_stats
        import agent.backend.rag as rag_mod
        stats = get_rag_stats()
        assert stats["status"] == "ok"
        assert "chunk_count" in stats


# ── auto_ingest_workspace ──────────────────────────────
class TestAutoIngest:
    @pytest.fixture(autouse=True)
    def reset_rag_globals(self, tmp_path, monkeypatch):
        import agent.backend.rag as rag_mod
        monkeypatch.setattr(rag_mod, "_chroma_client", None)
        monkeypatch.setattr(rag_mod, "_collection", None)
        monkeypatch.setattr(rag_mod, "RAG_STORE_DIR", str(tmp_path / "rag_store"))

    def test_auto_ingest_scans_workspace(self, tmp_path, monkeypatch):
        from agent.backend.rag import auto_ingest_workspace
        import agent.backend.rag as rag_mod
        import numpy as np

        # 模拟工作区
        (tmp_path / "README.md").write_text("# Test Project\nHello world", encoding="utf-8")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").write_text("部署说明...", encoding="utf-8")

        def mock_embed(texts):
            return [np.random.rand(1024).tolist() for _ in texts]

        monkeypatch.setattr(rag_mod, "_embed_texts", mock_embed)

        result = auto_ingest_workspace(str(tmp_path))
        assert result["status"] == "success"
        assert result["chunks_added"] > 0
        assert any("README" in s for s in result["sources"])


# ── tools.py rag_search 工具注册检查 ──────────────────
class TestToolRegistration:
    def test_rag_search_in_tools_list(self):
        from agent.backend.tools import tools
        names = [t["function"]["name"] for t in tools]
        assert "rag_search" in names

    def test_rag_search_in_available_functions(self):
        from agent.backend.tools import available_functions
        assert "rag_search" in available_functions
        assert callable(available_functions["rag_search"])
