# Independent positive-control transport review

On 2026-11-02 UTC `/root/ps1_execution_review` accepted the one fixed non-held NOIRLab transport: exact frozen query and effective URL, HTTP 200, TLS verify 0, no redirects or recorded overages, owned curl exit and released lease. Request, native/body/header/stream hashes, manifest/protocol references and RESULT-to-FINISH hash matched; the recorded PID was absent at review, custody/holdout coordination unchanged and no locks remained. The body was 3,121 bytes, SHA256 `4a2ca013b79bbe7bd1d57286f7504554f640139034c8f1e2dce35183a7f809f5`; native headers and diagnostics stay local.

A separate XML spot-check found status OK, exact echo, TableRows=1 and one 14-cell row containing the expected published Gaia and plate/MJD/fibre identifiers. This is not by itself acceptance of the positive control: strict field/null/integer/geometry checks and independent science review remain required. No original-held-source query was made.
