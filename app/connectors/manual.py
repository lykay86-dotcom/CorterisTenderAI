from __future__ import annotations
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from ftplib import FTP, FTP_TLS
from app.config.user_settings import PlatformConnection


class ManualConnectorTester:
    @staticmethod
    def test(connection: PlatformConnection, password: str = "", api_key: str = "") -> dict:
        try:
            protocol = connection.protocol.upper()
            if protocol == "API":
                headers = {"User-Agent": "CorterisTenderAI/1.2"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                req = Request(connection.endpoint, headers=headers)
                with urlopen(req, timeout=15) as resp:
                    return {
                        "ok": True,
                        "status": getattr(resp, "status", 200),
                        "content_type": resp.headers.get("Content-Type", ""),
                    }
            if protocol == "RSS":
                req = Request(connection.endpoint, headers={"User-Agent": "CorterisTenderAI/1.2"})
                with urlopen(req, timeout=15) as resp:
                    data = resp.read(1024 * 1024)
                root = ElementTree.fromstring(data)
                items = root.findall(".//item") or root.findall(
                    ".//{http://www.w3.org/2005/Atom}entry"
                )
                return {"ok": True, "items_found": len(items)}
            if protocol == "FTP":
                # endpoint: ftp://host/path or host/path
                endpoint = connection.endpoint.replace("ftp://", "").replace("ftps://", "")
                host, _, path = endpoint.partition("/")
                ftp = (
                    FTP_TLS(host, timeout=15)
                    if connection.endpoint.startswith("ftps://")
                    else FTP(host, timeout=15)
                )
                ftp.login(connection.username or "anonymous", password or "")
                if isinstance(ftp, FTP_TLS):
                    ftp.prot_p()
                if path:
                    ftp.cwd("/" + path)
                names = ftp.nlst()[:20]
                ftp.quit()
                return {"ok": True, "files_sample": names}
            return {"ok": False, "error": "Неизвестный протокол"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
