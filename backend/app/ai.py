import asyncio
import json
import time

import httpx


class AIError(Exception):
    pass


class OCRFormatError(AIError):
    """An unusable transcription, distinct from transport/auth/quota failure."""


PRIMARY_VISION_MODEL = "gpt-6-luna"


def vision_name(model):
    for prefix, name in (
        ("gpt-6-luna", "GPT-6 Luna"),
        ("gpt-4.1-mini", "GPT-4.1 mini"),
        ("gpt-5.6-sol", "GPT-5.6 Sol"),
    ):
        if model.startswith(prefix):
            return name
    return model


def vision_method(models, *, sol=False, pipeline="layout-v3"):
    names = {"6-luna" if model.startswith("gpt-6-luna") else "4.1-mini" for model in models}
    return "ocr+" + "+".join(sorted(names)) + ("+5.6-sol" if sol else "") + "-" + pipeline


def upstream_error(status, code=None):
    if status in (401, 403):
        return "Akses layanan AI belum aktif atau sudah berakhir. Silakan hubungi admin."
    if status == 429:
        if code == "relay_cost":
            return "Batas biaya uji layanan AI tercapai. Hasil pemrosesan yang sudah selesai tetap tersimpan."
        if code == "relay_budget":
            return "Kuota total relay tidak mencukupi untuk pemrosesan ini. Pemilik layanan perlu meninjau batas penggunaan."
        if code == "relay_rate":
            return "Batas permintaan relay per menit tercapai. Tunggu satu menit, lalu proses ulang."
        if code == "upstream_rate":
            return "Batas penggunaan OpenAI tercapai. Pemilik layanan perlu memeriksa saldo atau rate limit OpenAI."
        return "Batas penggunaan layanan AI tercapai. Silakan coba beberapa saat lagi."
    return "Layanan AI sedang tidak tersedia. Silakan coba kembali."


class Relay:
    def __init__(self, settings):
        self.settings = settings

    @property
    def headers(self):
        if not self.settings.ai_ready:
            raise AIError("Layanan AI belum dikonfigurasi. Admin perlu menghubungkan relay Cloudflare.")
        return {"Authorization": "Bearer " + self.settings.relay_token}

    def post(self, operation, payload):
        headers = self.headers
        for attempt in range(3):
            try:
                with httpx.Client(timeout=httpx.Timeout(90, connect=10), follow_redirects=False) as client:
                    response = client.post(self.settings.relay_url + "/" + operation, headers=headers, json=payload)
                if response.status_code in (502, 503, 504) and attempt < 2:
                    time.sleep(2**attempt)
                    continue
                if response.status_code != 200:
                    try:
                        code = response.json().get("code")
                    except (ValueError, AttributeError):
                        code = None
                    raise AIError(upstream_error(response.status_code, code))
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == 2:
                    raise AIError(
                        "Tidak dapat menghubungi layanan AI. Periksa koneksi internet dan konfigurasi relay."
                    ) from exc
                time.sleep(2**attempt)
        raise AIError("Layanan AI belum memberikan respons.")

    def embed(self, texts):
        result = self.post("embeddings", {"input": texts})
        try:
            data = sorted(result["data"], key=lambda item: item["index"])
            vectors = [row["embedding"] for row in data]
            if len(vectors) != len(texts) or any(len(vector) != 1536 for vector in vectors):
                raise ValueError("Invalid dimensions")
            return vectors
        except (KeyError, TypeError, ValueError) as exc:
            raise AIError("Format embedding layanan AI tidak sesuai.") from exc

    def vision(self, image, *, enhanced=False, fragment=False, structured=False):
        payload = {"images": image} if isinstance(image, list) else {"image": image}
        if enhanced:
            payload["enhanced"] = True
        if fragment:
            if not isinstance(image, str):
                raise AIError("Fallback Sol hanya menerima satu potongan gambar.")
            payload = {"image": image}
        if structured:
            payload["layout"] = True
        result = self.post("vision-fragment" if fragment else "vision", payload)
        try:
            choice = result["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("Incomplete OCR response")
            content = choice["message"]["content"]
            parsed = json.loads(content)
            if structured:
                if (
                    not isinstance(parsed, dict)
                    or not isinstance(parsed.get("blocks"), list)
                    or not 1 <= len(parsed["blocks"]) <= 128
                ):
                    raise ValueError("Invalid document layout")
                parsed["_model"] = result.get("model", "gpt-5.6-sol" if fragment else PRIMARY_VISION_MODEL)
                return parsed
            if not isinstance(parsed["text"], str) or not isinstance(parsed["uncertain"], bool):
                raise ValueError("Invalid OCR result")
            parsed["_model"] = result.get("model", "gpt-5.6-sol" if fragment else PRIMARY_VISION_MODEL)
            return parsed
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise OCRFormatError("Hasil bantuan OCR tidak dapat diverifikasi.") from exc

    async def answer(self, payload):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10), follow_redirects=False) as client:
                async with client.stream(
                    "POST", self.settings.relay_url + "/answer", headers=self.headers, json=payload
                ) as response:
                    if response.status_code != 200:
                        raise AIError(upstream_error(response.status_code))
                    finished = False
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        value = line[5:].strip()
                        if value == "[DONE]":
                            finished = True
                            break
                        packet = json.loads(value)
                        if "error" in packet:
                            raise AIError("Jawaban terputus dari layanan AI. Silakan coba kembali.")
                        for choice in packet.get("choices", []):
                            if choice.get("finish_reason") == "length":
                                raise AIError("Jawaban mencapai batas panjang. Silakan persempit pertanyaan.")
                            content = choice.get("delta", {}).get("content")
                            if content:
                                yield content
                    if not finished:
                        raise AIError("Jawaban belum selesai karena koneksi terputus. Silakan coba kembali.")
        except asyncio.CancelledError:
            raise
        except AIError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise AIError("Jawaban belum selesai. Periksa koneksi internet lalu coba kembali.") from exc
