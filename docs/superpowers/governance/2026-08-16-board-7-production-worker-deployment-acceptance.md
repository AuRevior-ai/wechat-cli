# Board 7 Production Worker Deployment Acceptance

Date: 2026-08-16
Gate: B7-G5 Production Worker Deploy
Status: ACCEPTED COMPLETE

## Canonical entry and source integration

B7-G4 Production Identity & Key Bootstrap entered B7-G5 from canonical main `13acc173b47355c0944d4c850b9e81384fd1bbc6`.

Pre-deploy review found one workflow-only wiring gap: the privileged production deployment workflow named the approved nine Worker runtime Secrets but did not materialize the approved atomic Secret bundle or pass it to `deploy_worker.py` / Wrangler via `--secrets-file`.

That wiring gap was repaired with TDD on `board7/production-worker-deploy`, committed as `8e514ab6062e8ef95c0e437b89b0062ce0f91083`, and history-preserving merged through PR #6 as canonical main `4608d8b850d081cf189449161ee30780eaa18c29`. Post-merge CI run `31920903252` passed. The production GitHub Environment then contained the existing five G4 Secrets plus one atomic transport Secret name, `PRODUCTION_WORKER_SECRETS_JSON`; the bundle value remained secret and was never committed or logged.

The workflow materializes that bundle only in runner temp, passes it through `--secrets-file`, and removes temporary deployment material in an `always()` cleanup step.

## Initial atomic production deployment

Exact source SHA: `4608d8b850d081cf189449161ee30780eaa18c29`

Production deploy workflow run: `31921033770`

Initial Worker Version ID: `6e03d11d-a5be-4f66-9684-ec21c45afe02`

The run passed exact canonical-main identity proof, fresh Python verification, fresh Worker verification, production trust-profile materialization, atomic Worker Secret bundle materialization, production preflight, deployment, and cleanup.

Post-deploy readback proved:

- Worker name `wechat-cli-license-update`;
- D1 binding `wechat-cli-license-production`, ID `011b3c26-bbe6-4bb7-8af7-39f1e6d46932`;
- R2 bindings `wechat-cli-releases-production` and `wechat-cli-diagnostics-production`;
- exactly the nine approved runtime Secret names;
- selectors remain V1;
- `workers_dev=false`;
- custom domains remain `wechat-cli-api.aurevior-devspace.com` and `wechat-cli-admin.aurevior-devspace.com`;
- distinct human and automation Access audiences remain configured;
- no production license, device, or release row was created by the deployment.

## Live ingress and human Access acceptance

Live production probes after deployment proved:

- API `/v1/health` returned HTTP 200 with `environment=production`;
- a native client route reached the real handler/auth layer and returned an expected request-validation error rather than an ingress error;
- API host access to admin and automation paths returned `403 INGRESS_NOT_ALLOWED`;
- the human admin login path returned a Cloudflare Access challenge for the exact human application audience;
- the automation path without a Service Token returned Cloudflare Access 403 for the exact automation application audience;
- admin-host access to a public client route returned `403 INGRESS_NOT_ALLOWED`;
- the production `workers.dev` hostname was unavailable and returned 404 / Cloudflare error 1042.

The repository's real human browser/PKCE login flow was exercised through Cloudflare Access. D1 readback independently proved the resulting principal and session contract:

- principal: `production-primary-admin`;
- status: active;
- session duration: exactly 1800 seconds;
- scopes exactly matched the approved human principal scope set.

During human Access diagnostics, one short-lived human Access JWT was accidentally emitted into transient tool output. It was not committed, written to repository files, or used as production application data. The production admin Access logout endpoint was immediately invoked, the documented propagation window was allowed to elapse, and the exposed session was not reused. A new non-exposed human session was then used for the successful 1800-second acceptance above.

## Service Token JWT compatibility defect and repair

The first real machine probe used the approved production Service Token credentials and reached the Worker but returned `AUTOMATION_IDENTITY_INVALID`.

Systematic debugging isolated the failure to the shared Access JWT verifier before D1 principal lookup. The production Service Token application JWT shape uses:

- `type="app"`;
- `common_name` as the Service Token Client ID identity;
- an empty string `sub`;
- no required `nbf` claim.

The shared verifier had been written for human Access assertions and incorrectly required both a non-empty `sub` and an `nbf` claim. This caused a valid Service Token assertion to fail before the configured automation identity allowlist and D1 principal checks.

A TDD repair introduced an explicit service-token verification mode used only by automation authentication. The machine path now requires the documented application-token shape while continuing to validate RS256 signature, trusted issuer/JWKS, exact automation audience, `type="app"`, exact `common_name` identity, time validity, configured identity allowlist, active D1 automation principal, and exact non-wildcard scope. Human Access verification retains the pre-existing non-empty subject / human assertion requirements.

Repair commit: `b4c7e6b49bb46c29768f0ef449d93099078d42d8`

History-preserving PR #7 merge / canonical main: `f760355779d05f59d1bcc81bd3dec40d38872be2`

PR and branch CI passed. Canonical-main post-merge CI run `31922860139` also passed.

Fresh local verification before integration passed:

- Python: 700 run / 2 expected skips / 0 failures;
- Worker typecheck: PASS;
- Worker Vitest: 18 files / 132 tests PASS;
- workflow policy: PASS;
- tracked sensitive-value scan: PASS;
- `git diff --check`: PASS.

## Repair redeployment and final machine acceptance

Exact repair source SHA: `f760355779d05f59d1bcc81bd3dec40d38872be2`

Production repair deploy workflow run: `31922922836`

Current accepted Worker Version ID: `ceedf5c8-111c-41e8-83f2-72733225352c`

The repair deployment again passed exact-main proof, fresh test execution, production trust-profile materialization, atomic Secret bundle materialization, fail-closed preflight, deployment, and unconditional cleanup.

Post-redeploy readback proved the nine Worker Secret names and production D1/R2/custom-domain bindings remained unchanged. Live smoke returned:

- API health HTTP 200 / production;
- API-to-automation ingress denial HTTP 403;
- admin-to-public-route ingress denial HTTP 403;
- production `workers.dev` unavailable;
- D1 business counts `licenses=0`, `devices=0`, `releases=0`;
- identity counts exactly one human principal and one automation principal.

The final real Service Token probe then succeeded:

`AUTOMATION_OK releases=0`

This proves the real production Cloudflare Service Token assertion is accepted by the repaired Worker and the approved automation principal can exercise its `releases:read` scope while production release count remains zero.

A same-credential human-route probe did not succeed, but the invoking PowerShell `Invoke-WebRequest` path returned no reliable HTTP status because of its legacy parsing prompt, so no exact 403/302 code is claimed from that one command. The machine/human boundary is nevertheless independently evidenced by the distinct Access applications/audiences, the live Access challenge/deny probes above, ingress route separation, the automation-only `access_service` authentication path, and the exact three-scope automation principal with no human admin scopes.

## Accepted terminal state

B7-G5 is accepted complete.

Accepted production state at closure:

- canonical main: `f760355779d05f59d1bcc81bd3dec40d38872be2`;
- production Worker current Version ID: `ceedf5c8-111c-41e8-83f2-72733225352c`;
- production API health live;
- production custom-domain ingress boundaries live;
- production `workers.dev` unavailable;
- human Access login accepted with an exact 30-minute `wcas` session;
- machine Service Token authentication accepted only through the automation authentication path;
- production D1 still contains zero licenses, zero devices, and zero releases;
- production R2 contains no B7-G6 release mutation yet;
- no release was registered, enabled, paused, rolled out, or published during G5.

Next gate: B7-G6 CI/CD Automation Acceptance. The first permitted production release-preparation target remains stable `0.6.0`, which must be built from the exact accepted canonical main, published as immutable private provenance, uploaded to production R2, and registered terminally `enabled=false` / `paused=true`; B7-G6 still does not authorize release enablement.
