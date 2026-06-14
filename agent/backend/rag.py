"""RAG 知识增强模块：文档加载、切分、向量化存储与检索。"""

import hashlib
import os
import re
from numbers import Real
from typing import Any, Dict, List, Optional, Tuple

from agent.backend.config import (
    RAG_STORE_DIR,
    RAG_DEFAULT_TOP_K,
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
    RAG_COLLECTION_NAME,
)


# ── 全局 Chroma 客户端（懒加载）────────────────────────
_chroma_client = None
_chroma_client_signature: Optional[Tuple[Any, ...]] = None
_collection = None


def _get_chroma_mode() -> str:
    """读取 ChromaDB 运行模式。

    支持：
      - http:       连接 Docker 或独立 ChromaDB 服务
      - memory:     仅在当前 Python 进程中保存数据，适合临时测试
      - persistent: 使用本机持久化模式

    当前 Windows 环境建议使用 http 模式。
    """
    return os.getenv("CHROMA_MODE", "http").strip().lower()


def _get_client_signature() -> Tuple[Any, ...]:
    """生成客户端配置签名。

    当环境变量发生变化时，自动重建客户端，避免继续复用旧连接。
    """
    mode = _get_chroma_mode()

    if mode == "http":
        return (
            mode,
            os.getenv("CHROMA_HOST", "localhost"),
            int(os.getenv("CHROMA_PORT", "8001")),
            os.getenv("CHROMA_SSL", "false").strip().lower() == "true",
        )

    if mode == "persistent":
        return (
            mode,
            os.path.abspath(os.getenv("CHROMA_PATH", RAG_STORE_DIR)),
        )

    if mode == "memory":
        return (mode,)

    raise ValueError(
        f"不支持的 CHROMA_MODE={mode!r}。"
        "可用值：http、memory、persistent"
    )


def reset_chroma_cache() -> None:
    """清空当前进程中的 Chroma 客户端缓存。

    修改 CHROMA_MODE、CHROMA_HOST 或 CHROMA_PORT 后，
    可以调用此函数强制重新创建客户端。
    """
    global _chroma_client
    global _chroma_client_signature
    global _collection

    _collection = None
    _chroma_client = None
    _chroma_client_signature = None


def _get_chroma_client():
    """懒加载 ChromaDB 客户端。"""
    global _chroma_client
    global _chroma_client_signature
    global _collection

    signature = _get_client_signature()

    if (
        _chroma_client is not None
        and _chroma_client_signature == signature
    ):
        return _chroma_client

    import chromadb

    # 客户端配置变化后，不应继续使用旧 collection。
    _collection = None

    mode = signature[0]

    if mode == "http":
        _, host, port, ssl = signature
        _chroma_client = chromadb.HttpClient(
            host=host,
            port=port,
            ssl=ssl,
        )

        # 尽早检查 Docker 中的 ChromaDB 是否可访问。
        _chroma_client.heartbeat()

    elif mode == "memory":
        _chroma_client = chromadb.EphemeralClient()

    elif mode == "persistent":
        _, store_path = signature
        os.makedirs(store_path, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=store_path)

    else:
        raise ValueError(f"不支持的 ChromaDB 模式：{mode}")

    _chroma_client_signature = signature
    return _chroma_client


def _get_collection():
    """获取或创建默认 collection。"""
    global _collection

    if _collection is not None:
        return _collection

    client = _get_chroma_client()
    _collection = client.get_or_create_collection(
        name=RAG_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


# ── 文档加载 ──────────────────────────────────────────
def load_pdf(path: str) -> str:
    """读取 PDF 文件，返回纯文本。"""
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages: List[str] = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    return "\n\n".join(pages)


def load_markdown(path: str) -> str:
    """读取 Markdown 或纯文本文件，返回原文。"""
    with open(path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read()


def load_file(path: str) -> str:
    """根据文件扩展名自动选择加载方式。"""
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        return load_pdf(path)

    if ext in (".md", ".txt", ".markdown"):
        return load_markdown(path)

    # 未知格式：尝试作为纯文本读取。
    try:
        return load_markdown(path)
    except Exception:
        return ""


# ── 文本切分 ──────────────────────────────────────────
def split_chunks(
    text: str,
    source: str,
    chunk_size: int = RAG_CHUNK_SIZE,
    chunk_overlap: int = RAG_CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """将文本切分为多个块，并保留来源信息。

    返回格式：
        [
            {
                "content": "...",
                "source": "...",
                "chunk_index": 0,
            }
        ]
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap 不能小于 0")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须小于 chunk_size")

    paragraphs = re.split(r"\n{2,}", text)
    chunks: List[Dict[str, Any]] = []

    current = ""
    chunk_index = 0

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        # 当前段落可以直接拼接到已有内容。
        if len(current) + len(paragraph) + 2 <= chunk_size:
            current = (
                f"{current}\n\n{paragraph}"
                if current
                else paragraph
            )
            continue

        # 先保存之前累计的短段落。
        if current:
            chunks.append(
                {
                    "content": current,
                    "source": source,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1
            current = ""

        # 单个段落过长时，使用滑动窗口强制切分。
        if len(paragraph) > chunk_size:
            start = 0

            while start < len(paragraph):
                end = min(start + chunk_size, len(paragraph))

                chunks.append(
                    {
                        "content": paragraph[start:end],
                        "source": source,
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1

                if end >= len(paragraph):
                    break

                start = end - chunk_overlap

        else:
            current = paragraph

    if current:
        chunks.append(
            {
                "content": current,
                "source": source,
                "chunk_index": chunk_index,
            }
        )

    return chunks


# ── Embedding 函数 ────────────────────────────────────
def _embed_texts(texts: List[str]) -> List[List[float]]:
    """调用 OpenAI 兼容的 Embedding API 对文本列表进行向量化。"""
    from agent.backend.llm import get_embeddings

    return get_embeddings(texts)


def _normalize_embeddings(
    embeddings: List[List[float]],
    expected_count: int,
) -> List[List[float]]:
    """校验并标准化 Embedding 列表。"""
    if len(embeddings) != expected_count:
        raise ValueError(
            "Embedding 数量不一致："
            f"预期 {expected_count} 条，实际 {len(embeddings)} 条"
        )

    if not embeddings:
        raise ValueError("Embedding 列表不能为空")

    dimensions = set()
    normalized: List[List[float]] = []

    for index, embedding in enumerate(embeddings):
        if not embedding:
            raise ValueError(f"第 {index} 条 Embedding 为空")

        dimensions.add(len(embedding))

        normalized_embedding: List[float] = []

        for value in embedding:
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError(
                    f"Embedding 中存在非数值类型：{type(value).__name__}"
                )

            normalized_embedding.append(float(value))

        normalized.append(normalized_embedding)

    if len(dimensions) != 1:
        raise ValueError(
            f"Embedding 维度不一致：{sorted(dimensions)}"
        )

    return normalized


def _build_chunk_id(chunk: Dict[str, Any]) -> str:
    """为文档块生成稳定且不会跨文档冲突的 ID。

    同一个文件的同一个 chunk_index 再次入库时会覆盖旧内容，
    避免每次重复入库都增加重复记录。
    """
    source = os.path.abspath(str(chunk["source"]))
    chunk_index = int(chunk["chunk_index"])

    raw_id = f"{source}|{chunk_index}"
    digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()

    return f"chunk_{digest}"


# ── 入库 ──────────────────────────────────────────────
def ingest_documents(doc_paths: List[str]) -> Dict[str, Any]:
    """加载、切分、向量化并写入多个文档。

    参数：
        doc_paths: 文件路径列表，支持 PDF、Markdown 和纯文本。

    返回：
        {
            "status": "success",
            "chunks_added": 10,
            "sources": [...],
            "errors": [...],
        }
    """
    all_chunks: List[Dict[str, Any]] = []
    sources: List[str] = []
    errors: List[str] = []

    for path in doc_paths:
        if not os.path.isfile(path):
            message = f"跳过不存在的文件：{path}"
            print(f"[RAG] {message}")
            errors.append(message)
            continue

        try:
            text = load_file(path)

            if not text.strip():
                message = f"文件内容为空：{path}"
                print(f"[RAG] {message}")
                errors.append(message)
                continue

            chunks = split_chunks(text, source=path)
            all_chunks.extend(chunks)
            sources.append(path)

        except Exception as error:
            message = f"加载文件失败 {path}：{error}"
            print(f"[RAG] {message}")
            errors.append(message)

    if not all_chunks:
        return {
            "status": "error",
            "message": "没有可入库的文档内容",
            "chunks_added": 0,
            "sources": sources,
            "errors": errors,
        }

    try:
        collection = _get_collection()
    except Exception as error:
        message = f"无法连接 ChromaDB：{error}"
        print(f"[RAG] {message}")

        return {
            "status": "error",
            "message": message,
            "chunks_added": 0,
            "sources": sources,
            "errors": errors + [message],
        }

    batch_size = 100
    added = 0

    for start in range(0, len(all_chunks), batch_size):
        batch = all_chunks[start:start + batch_size]

        texts = [chunk["content"] for chunk in batch]
        ids = [_build_chunk_id(chunk) for chunk in batch]
        metadatas = [
            {
                "source": chunk["source"],
                "chunk_index": int(chunk["chunk_index"]),
            }
            for chunk in batch
        ]

        try:
            raw_embeddings = _embed_texts(texts)
            embeddings = _normalize_embeddings(
                raw_embeddings,
                expected_count=len(texts),
            )

            if not (
                len(ids)
                == len(texts)
                == len(embeddings)
                == len(metadatas)
            ):
                raise ValueError(
                    "写入 ChromaDB 前的数据数量不一致："
                    f"ids={len(ids)}, "
                    f"texts={len(texts)}, "
                    f"embeddings={len(embeddings)}, "
                    f"metadatas={len(metadatas)}"
                )

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

            added += len(batch)

        except Exception as error:
            message = f"写入 ChromaDB 批次 {start} 失败：{error}"
            print(f"[RAG] {message}")
            errors.append(message)

    if added == 0:
        return {
            "status": "error",
            "message": "所有文档块均写入失败",
            "chunks_added": 0,
            "sources": sources,
            "errors": errors,
        }

    return {
        "status": "success",
        "chunks_added": added,
        "sources": sources,
        "errors": errors,
    }


def auto_ingest_workspace(workspace_dir: str) -> Dict[str, Any]:
    """自动扫描工作区中的文档并入库。

    扫描规则：
      - workspace_dir 下的 README.md
      - workspace_dir/docs/ 下所有 .md、.txt、.markdown 文件
      - workspace_dir/agent/docs/ 下所有 .md、.txt、.markdown 文件
      - workspace_dir 根目录下所有 PDF 文件
    """
    if not os.path.isdir(workspace_dir):
        return {
            "status": "error",
            "message": f"工作区目录不存在：{workspace_dir}",
            "chunks_added": 0,
            "sources": [],
        }

    doc_paths: List[str] = []

    # README.md
    readme = os.path.join(workspace_dir, "README.md")

    if os.path.isfile(readme):
        doc_paths.append(readme)

    # docs/ 目录
    docs_dir = os.path.join(workspace_dir, "docs")

    if os.path.isdir(docs_dir):
        for root, _, files in os.walk(docs_dir):
            for filename in files:
                if filename.lower().endswith(
                    (".md", ".txt", ".markdown")
                ):
                    doc_paths.append(
                        os.path.join(root, filename)
                    )

    # agent/docs/ 目录
    agent_docs_dir = os.path.join(
        workspace_dir,
        "agent",
        "docs",
    )

    if os.path.isdir(agent_docs_dir):
        for root, _, files in os.walk(agent_docs_dir):
            for filename in files:
                if filename.lower().endswith(
                    (".md", ".txt", ".markdown")
                ):
                    doc_paths.append(
                        os.path.join(root, filename)
                    )

    # 根目录下 PDF
    for filename in os.listdir(workspace_dir):
        if filename.lower().endswith(".pdf"):
            doc_paths.append(
                os.path.join(workspace_dir, filename)
            )

    # 避免同一路径被重复扫描。
    unique_doc_paths = list(dict.fromkeys(doc_paths))

    return ingest_documents(unique_doc_paths)


# ── 检索 ──────────────────────────────────────────────
def rag_search(
    query: str,
    top_k: int = RAG_DEFAULT_TOP_K,
) -> Dict[str, Any]:
    """执行 RAG 检索，返回最相关的文本块。"""
    if not query or not query.strip():
        return {
            "query": query,
            "top_k": top_k,
            "results": [],
            "error": "检索查询不能为空",
        }

    if top_k <= 0:
        return {
            "query": query,
            "top_k": top_k,
            "results": [],
            "error": "top_k 必须大于 0",
        }

    try:
        collection = _get_collection()
        count = collection.count()

        if count == 0:
            return {
                "query": query,
                "top_k": top_k,
                "results": [],
                "message": (
                    "知识库为空，请先调用 ingest_documents "
                    "或 auto_ingest_workspace 入库文档"
                ),
            }

        query_embedding = _normalize_embeddings(
            _embed_texts([query]),
            expected_count=1,
        )[0]

        chroma_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        documents = chroma_results.get("documents", [[]])[0]
        metadatas = chroma_results.get("metadatas", [[]])[0]
        distances = chroma_results.get("distances", [[]])[0]

        results: List[Dict[str, Any]] = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):
            score = round(1.0 - float(distance), 4)

            results.append(
                {
                    "content": document or "",
                    "source": (metadata or {}).get(
                        "source",
                        "unknown",
                    ),
                    "score": score,
                }
            )

        return {
            "query": query,
            "top_k": top_k,
            "results": results,
        }

    except Exception as error:
        return {
            "query": query,
            "top_k": top_k,
            "results": [],
            "error": f"RAG 检索失败：{error}",
        }


def get_rag_stats() -> Dict[str, Any]:
    """返回当前知识库统计信息。"""
    try:
        collection = _get_collection()
        mode = _get_chroma_mode()

        result: Dict[str, Any] = {
            "status": "ok",
            "collection": RAG_COLLECTION_NAME,
            "chunk_count": collection.count(),
            "mode": mode,
        }

        if mode == "http":
            result["host"] = os.getenv(
                "CHROMA_HOST",
                "localhost",
            )
            result["port"] = int(
                os.getenv("CHROMA_PORT", "8001")
            )

        elif mode == "persistent":
            result["store_dir"] = os.path.abspath(
                os.getenv("CHROMA_PATH", RAG_STORE_DIR)
            )

        return result

    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "chunk_count": 0,
            "mode": _get_chroma_mode(),
        }
