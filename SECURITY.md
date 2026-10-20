# Security — PTPGE MCP server

The PTPGE MCP server (`org.ptpge/mcp-server`) is a **read-only reference server for an open specification**. It holds no customer data, needs no key to read, and writes to nothing of yours. This page answers the five questions a print business is advised to ask any MCP vendor (agenticprint.org, *MCP Security Checklist for Print Businesses*, October 2026) — honestly, including where the answer is «not yet».

## 1 · Do you sign your releases?

Releases are tagged in git (`v<version>`) and published through the official MCP registry. **Signed releases (Sigstore) are being set up** — until they are live, verify by comparing the tag's commit hash with the registry entry. This section will say «yes» when it is true, not before.

## 2 · How fast do you repair a critical vulnerability, and how do you tell us?

- **Report** to **security@ptpge.org**. Do not open a public issue for a vulnerability. We acknowledge within 2 working days.
- **Fix:** a confirmed critical issue gets a fix release within 7 days; others in the next regular release.
- **Tell:** a GitHub Security Advisory on the repository (which carries a CVE where applicable), a CHANGELOG entry, and a line in this file. Subscribe to the repository's security advisories to be notified.

## 3 · Can we export the logs in a structured format?

The hosted server (`mcp.ptpge.org`) keeps ordinary access logs only (time, tool, IP) and does not know on whose behalf an agent calls — by design. **The audit log you need — who asked the agent to do what, with which inputs and results — lives in your MCP client or gateway**, and that is where to export it from. Every tool here returns structured JSON with stable field names, so such a log is machine-readable.

## 4 · Can we limit each tool to read-only access?

Yes. Every tool carries MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) that a client or gateway can enforce.

| Tool | read-only | notes |
|---|---|---|
| `ptpge_search_terms`, `ptpge_get_term`, `ptpge_browse`, `ptpge_get_version`, `ptpge_get_product_envelope`, `ptpge_validate_config`, `ptpge_resolve_color_notation`, `ptpge_expand_fingerprint` | yes | pure lookups and computations |
| `ptpge_check_domain` | yes | reads a third-party domain (`openWorldHint`) |
| `ptpge_validate_document` | yes | fetches schemas from ptpge.org (`openWorldHint`) |
| **`ptpge_fingerprint`** | **no** | computes the identity **and registers the spec-profile fingerprint in the public register** at ptpge.org/f — no personal data, same configuration → same entry, idempotent, not undoable. Declared `readOnlyHint=false` so your client can require approval. |

## 5 · Can we turn off the tools we do not need?

Your MCP client decides which tools the agent sees; the server cannot and should not. To choose:

- Look up terms only → `search_terms`, `get_term`, `browse`, `get_version`.
- Validate and identify a configuration → add `get_product_envelope`, `validate_config`, `fingerprint`.
- Check a supplier or a document → `check_domain`, `validate_document`.

**File reading is not in the default tool list.** The artwork reader (`POST /artwork`) exists as an HTTP endpoint for the storefront demo and is deliberately not exposed as an MCP tool; it reads PDF structures (boxes, colour spaces, output intents), never page text, and every string it echoes from a file is sanitised and capped.

## Prompt injection

Nothing this server returns is built from free text in a customer file. Term labels and definitions come from the vocabulary; tool results are structured. Where a string originates in a file (a separation name, an OutputIntent identifier), it is reduced to printable characters and capped before it is echoed. Your agent should still treat any document content as data, not instructions — that is a client-side rule, and the reference storefront labels uploaded document text accordingly.

## What this server is not

It is not a gateway, not a MIS connector, and not a place where orders, prices or files are stored. It answers questions about the specification. Anything that writes into your systems is somebody else's server, and this checklist applies to that one too.

*Current for server 0.40.1, 20 October 2026. Changes to this file are listed in CHANGELOG.md.*
