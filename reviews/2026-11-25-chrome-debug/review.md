# Review of `chrome-debug`

## Resolution of the second review, 2026-11-25 (Claude)

**Status: all three blockers and all three other findings are fixed, with regression tests.** Fixed in the working tree on top of `a465eeb`. Regression suite: [`tests/chrome-debug/run.sh`](../../tests/chrome-debug/run.sh), 50 cases, all passing.

| Finding | Fix | Regression cases (`run.sh`) |
| --- | --- | --- |
| **Lock timeout and cancellation** | `acquire_launch_lock \|\| exit 1` runs before port selection. HUP/INT/TERM handlers exit (129/130/143), and only the `EXIT` trap releases the lock, and only a lock this PID holds. A dead holder's lock is taken over, as is a lock dir with no PID after a minute. Wait is 40 s (`CHROME_DEBUG_LOCK_WAIT`). | lock timeout ×5, TERM while waiting ×3, stale takeover ×2, TERM during startup ×4, concurrent launches ×2 |
| **Endpoint attributed to the wrong profile** | Ownership now needs the listening socket's PID: `/proc/net/tcp` inode found in the browser's `/proc/<pid>/fd` (Linux), `Get-NetTCPConnection` OwningProcess (Windows), `lsof -t` (macOS). Launch readiness, attach-with-profile, profile/port/global `--status` and `--list` all require it. They wait or fail while the owner is unknown, and fail at once when another PID owns the socket. A failed launch always cleans up its own profile's browser. `verify_port_owner` and its `DevToolsActivePort` check are gone: live Chromium 156 does not write that file for an explicit `--remote-debugging-port`, so it never fired. | two-claimant status/attach/stop ×11, decoy listener at launch ×4 |
| **Stop selects unrelated executables** | Catch-all `*-chrome`/`*-chromium` names removed. A row exists only when the process's real executable (`/proc/<pid>/exe`, or `ps comm` on macOS) is an exact Chrome/Chromium name. Immediately before `kill`, the PID is re-checked as a browser on that port. Stop succeeds when the signalled PIDs are gone (and, for a bare port, the endpoint closed). An answering port with no browser of ours is reported and left alone. | `export-chrome`, logger and spoofed-argv[0] processes ×8 |
| `--list` overstates readiness | Host-specific probe plus listener ownership per running profile: `● port N` / `◌ … starting or not answering` / `✖ … answered by another process`. | list ×3, status of a closed endpoint ×2 |
| Display name in the account column | jq emits `-` for empty fields, so the tab-delimited `read` can't collapse them. The `Default/Preferences` email is then used. | list ×1 |
| Symlink followed by `..` | `canonical_path` walks the existing leading components through the kernel (`[ -d ]`, then `cd -P`), then normalizes only the missing suffix. | symlink/.. ×3 |

**Found while testing (also fixed):** under WSL2 mirrored networking, a connection to a closed loopback port times out (curl 28) instead of being refused. Linux-host probes therefore reported "port conflict" for a starting browser and free ports as busy. `cdp` now checks the Linux socket table first for the Linux host, and treats a timeout with no Linux listener as closed.

**Also added:** `CHROME_DEBUG_CHROME` selects the browser binary (Linux Chromium under WSL, Chrome for Testing). The suite uses it to run the Linux path on WSL.

### Verification

| Check | Result |
| --- | --- |
| Regression suite | 50/50 pass in ~30 s, using a stand-in browser (python3 copied as `chrome`) that really owns its socket. |
| Mutation check | Each original bug was re-introduced into a temporary copy, one at a time, and each one failed its own cases: lock timeout continues (4 failed), INT/TERM traps continue (4), ownership always true (9), browser identity by command-line name suffix (3), tab-collapsed account fields (1), lexical `..` (2), `--list` trusting the process (2). |
| Live Linux Chromium 156 (WSL kernel, Windows tools on PATH) | Headless launch on 39990 with a profile path containing a space, attach with URL, status by dir and by port, stop by dir. Afterwards the socket and processes were gone. |
| Live Windows Chrome 158 from WSL2 (mirrored) | Headless launch on 9231 in a `%TEMP%` directory containing spaces, attach with URL, status by dir, stop by dir. Afterwards there were 0 listeners and 0 matching `chrome.exe` processes. |
| Repo checks | `bash -n`, `git diff --check` and `./install.sh --check` (exit 0, `ss` and `python3` recognized) pass. |

Coverage limits: macOS paths (`lsof`, `ps comm`) were reviewed but not run. WSL2 NAT mode was not run.

### Next steps

**Pramit:** commit and push (command in the session reply). Nothing else is open.

## Second review, 2026-11-25

**Recommendation: hold the merge.** The revised launcher passes the normal browser lifecycle on Windows and Linux. Three problems remain in the paths that protect profile selection and process termination.

Reviewed [the launcher](../../common/.local/bin/chrome-debug) at Git blob `2cace2eec9b1ab69bce4babd433979c01ab90ac0`, along with its [README](../../README.md) and [dependency manifest](../../deps.list). Line numbers in this section refer to that launcher revision.

### Merge blockers

| Finding | Observed behavior | Required change |
| --- | --- | --- |
| **High — Lock timeout and cancellation allow launch to proceed** (lines 1278–1296, 1358) | With a live holder in the fixture’s lock directory, a second invocation waited 20 seconds, then launched successfully while the original holder still owned the lock. A separate invocation received `SIGTERM` after acquisition, released the lock and continued to launch. Ordinary concurrent launches did pick separate ports. | Make failure to acquire the lock exit before port selection. Have the interrupt and termination handlers exit, and release the lock on exit. Retain tests for timeout and cancellation as well as ordinary contention. |
| **High — A responding endpoint can be attributed to the wrong profile** (lines 989–995, 1012–1015, 1336–1354, 1363–1377, 1502–1518) | A controlled launch with a live child, an answering endpoint, no discovered owner and no profile port file reported “session active.” With two browser parent records claiming the same host and port for different directories, profile-specific status displayed the shared endpoint’s tabs under either directory and attach sent a tab request. Only one process can own a particular listening socket. The checks accept a matching command line, a port number left in a file, or a still-running child as proof. | Require positive evidence linking the endpoint to the selected profile, such as its actual listening PID or a matching browser-specific DevTools identifier. While ownership is unknown or ambiguous, wait or fail before reporting readiness, reading tabs or opening one. |
| **High — Stop still selects unrelated executables** (lines 662–675, 1104–1111, 1123–1134) | The original logger case is fixed. A process-table fixture with an unrelated helper called `export-chrome` and a matching port argument still sent that PID to the intercepted `kill`. The later shutdown check reported failure only after the signal had been requested. | Remove the catch-all executable suffixes. Verify the actual browser executable and selected process identity before signaling. Keep both unrelated-process cases as regressions. |

### Other remaining findings

- **Profile listing still overstates readiness** (lines 847–857, 1086–1089). With a browser process present and its endpoint closed, global `--status` correctly returned 1, while `--list` displayed `● port 9222`. Use a host-specific health check or label the process as starting or unreachable.
- **A display name can appear in the account column** (lines 801–823). When `Local State` contained an empty email and a display name, the tab-delimited shell read shifted the name into the email field. The launcher skipped the valid email in `Default/Preferences`. Preserve empty JSON fields when transferring them to Bash.
- **A symlink followed by `..` can open the wrong file** (lines 137–175, 905–923). With `parentlink` pointing to `physical/nested`, the existing `parentlink/../page.html` became a URL for `page.html` in the caller’s directory. Resolve existing path components in filesystem order before appending any missing suffix. This helper also computes profile directories.

### Verification of the revision

| Area | Result |
| --- | --- |
| Live Windows Chrome 158 from WSL2 | Headless launch on 9231, lookup by directory containing a space, attach, tab listing and profile-specific stop passed. An independent Windows request confirmed the endpoint closed, and zero matching processes remained. A separate launch on port 46147 failed to bind, printed Chrome’s bind error, port and profile, and cleaned up its processes. |
| Live Linux Chromium 156 | Exercised the native Linux branch on the WSL2 kernel with a disposable profile. Launch, profile lookup, attach, tab listing and stop passed. The socket closed. |
| 40 expected-behavior CLI cases | All passed. Coverage included failed listener inventory, ordinary concurrent allocation, conflicting explicit selectors on launch/status/stop, separate WSL hosts sharing a port, duplicate profile roots and label paths, indented account JSON, port overflow, and encoded local files on both launch and attach. The captured launch arguments omitted the wildcard origin override. |
| 9 additional CLI cases | Reproduced the remaining behavior documented above using controlled process tables, HTTP responses, lock state and profile metadata. Stop-selection tests intercepted signals. |
| Repo checks and coverage limits | Bash syntax, `git diff --check`, and `./install.sh --check` passed. The installer recognized optional `ss`. macOS and split-host WSL networking received fixture coverage only. The test harness was temporary. |

### Next steps

**Agy, before merge:** fix the three blockers and keep regression tests for the failing cases. Address the three list, account and path findings in the revision as well.

<details>
<summary>First review, prior launcher revision 0616701</summary>

**Recommendation: hold the change.** Both real browsers passed the ordinary launch-to-stop flow. The blocker is account selection. A failed port scan or simultaneous launch can make the command report success for one profile while another profile owns the endpoint. The stop path can also signal the wrong process.

Reviewed on 2026-11-25 against [the working-tree launcher](../../common/.local/bin/chrome-debug), Git blob `061670195716c94788224abef41b2dcb28fc67ba`, based on `8853424`. Line numbers below refer to that blob.

## Findings to fix before merge

| Priority | Where | Evidence and recommended fix |
| --- | --- | --- |
| High | Auto-port selection and readiness, lines 393–417, 709–745, 823–843 | With profile A serving port 9222 and the installed `ss` returning an error, a request for B opened a tab on A and printed B’s directory. The committed launcher skipped 9222 under the same fixture. Separately, two simultaneous launches for fresh profiles both picked 9222 and both reported success when one endpoint became ready. Preserve inventory errors, retry occupied candidates, and verify the answering browser belongs to the requested directory before sending URLs or reporting readiness. Serialize allocation through startup or let Chrome allocate the port and read it from the requested profile. |
| High | Explicit port with a profile, lines 582–585, 678–681, 731–745 | With A on 9222, requesting B with `-p 9222` opened a tab in A. The corresponding stop selected A’s PID and printed B’s directory. This behavior predates the diff. When the user supplies both identifiers, require them to resolve to the same session. A mismatch should fail before opening a tab, showing another account’s tabs, or sending a signal. |
| High | Stop process selection, lines 642–674 | The Unix process filter searches the entire command line for `chrom` and the port flag. A process-table fixture containing an unrelated logger satisfied both conditions. The launcher sent its PID to the intercepted `kill` and printed “Stopped” even though no endpoint had been active. Windows also emits a PID before confirming that `Stop-Process` succeeded. Validate the browser executable and exact arguments, target its parent PID, and verify termination before reporting success. |
| High | WSL sessions sharing a port, lines 289–318, 420–463, 645–657 | In a split-network fixture, a Linux browser and a Windows browser both used 9222. Deduplication kept the Linux row and lookup by the Windows profile failed. The HTTP path also prefers Linux, while stop-by-port targets both hosts. Carry the host, PID, profile directory and port together through discovery, HTTP and stop. Require disambiguation for a bare port that identifies two browsers. |
| High | Browser launch flags, lines 770–776 | Every launch passes `--remote-allow-origins=*`, including launches with persistent signed-in profiles. This disables Chromium’s DevTools WebSocket origin check for clients that can reach the endpoint. Remove the wildcard default. If a supported client needs an explicit origin, scope it to that client. This flag predates the diff. [Chromium’s origin check](https://chromium.googlesource.com/chromium/src/+/7bdbd0785b19711cad102fe391865bbba8718db9/content/browser/devtools/devtools_http_handler.cc) |

## Other fixes

- **Preserve WSL profile identity across both roots** (lines 263–276, 500–519, 620–636). With the same name under both homes, the old named launch selected the Linux-home profile. The new launch silently selected the Windows copy, while `--list` printed two indistinguishable names. With only a legacy profile present, launch reused it correctly, but the manual account-label hint pointed at the Windows home. Show the real directory for collisions and label hints, and require an explicit directory for an ambiguous name. Update the home-directory examples in [the README](../../README.md) and `--help` to describe Windows Chrome’s new default.
- **Report startup bind failures accurately** (lines 321–335, 823–850). On two explicit high ports Windows Chrome stayed running with the requested flags and a fresh profile. Windows reported zero listeners, both Windows and WSL HTTP failed, and a separate Windows bind attempt later returned “address already in use” on both ports. Neither port appeared in the reported IPv4 exclusion ranges. The launcher timed out and suggested mirrored networking. Preserve browser startup diagnostics, show the profile and port on failure, and handle the browser the invocation started. The underlying Windows reservation mechanism was undetermined.
- **Make status reflect endpoint health** (lines 503–517, 597–609). With a matching process and a closed endpoint, global `--status` printed “No Chrome debug session active” and exited 0. `--list` displayed a running port for the same fixture. Return failure when no discovered endpoint answers and distinguish a starting or unreachable process from a ready session.
- **Normalize paths once** (lines 263–269, 466–482, 537–542, 697–705). An absolute process directory and a request for the same directory using `./` failed to match. An existing `./notes.html` became `https://./notes.html` on attach. Compare canonical profile paths and convert local file arguments to correctly encoded `file:` URLs for the browser’s OS on both launch and attach.
- **Parse account metadata as JSON** (lines 485–488, 509–515). A compact `Local State` fixture showed its account. The same fields in indented JSON produced “not signed in to Chrome.” Use the existing `jq` dependency to read the intended profile record and preserve the `.account` override.
- **Reject oversized decimal ports before shell arithmetic** (lines 169–177). Input `18446744073709551617` produced two integer diagnostics, wrapped to 1, and probed port 1. Strip leading zeroes and check the significant digit count before converting. Keep support for valid inputs such as `09222`.
- **Declare the Linux listener inventory tool.** The launcher uses `ss` when available. Add its optional Linux/WSL dependency to [the manifest](../../deps.list) when fixing the scan fallback.

## Verification

| Test | Result |
| --- | --- |
| Live Windows Chrome 158.0.8127.37 from WSL2 | On bindable port 9231, headless launch with a disposable directory containing a space, status by directory, tab creation, tab listing and stop by directory all passed. An independent Windows HTTP request confirmed readiness. After stop, the endpoint was down and the matching Windows process count was zero. Two high-port failures are recorded above. |
| Live Linux Chromium 156.0.8078.4 | Exercised the native Linux branch on the WSL2 kernel with cached Chromium on an isolated PATH and WSL detection disabled. Headless launch, lookup by directory, attach, status with both expected tabs, and stop all passed. The socket closed. All live test profiles were temporary and cleaned up. |
| 41 controlled CLI cases | Ran the launcher entry point with temporary homes and controlled process, port and HTTP responses. Cases covered argument errors, aliases, port conflicts and exhaustion, races, account discovery, Unicode and URL encoding, partial tab failure, WSL fallback and dual roots, and macOS listener parsing. The unsafe outcomes above are observations from these cases. Stop-selection fixtures intercepted signals. The first 33 cases were also run against the committed launcher for comparison. |
| Repo checks | `bash -n common/.local/bin/chrome-debug`, `git diff --check`, and `./install.sh --check` passed. The installer check had Windows interop available and confirmed the launcher link and required dependencies. |

Native macOS launch and a separate WSL2 NAT installation were outside live coverage. The macOS listener and Windows-only HTTP fallback paths received fixture coverage.

</details>
