# Feature verification

Apply `workflows/contracts/verification-base.md` for the shared `AC-n` evidence types, reachability, head identity, and result-comment publication. This reference adds feature coverage checks, dispositions, and gap routing.

The issue's `AC-n` criteria are the claims. One fresh verifier, independent of the builders and reviewers, works at the frozen full-SHA participating commit map. It uses clean detached checkouts and runs the profile quality commands, every Regression Guard command, and the issue's named journeys itself. It reads the current issues, the plan, builders' coverage maps, tests, and its own command output. The manager runs no verification command and authors no result text.

For each check-decided `AC-n`, report `pass`, `gap`, `fail`, or `not_verified` with a one-line locator to a test and output or journey step. `gap` means the behavior appears present but a regression would escape the checks that ran. `fail` requires a demonstrated product defect or broken Regression Guard and its reproduction. `not_verified` means the applicable check could not run; an unrun or broken check returns to the verifier before an outcome is set. A visible-user criterion needs a rendering test or journey step. A check that can skip must show that its query actually ran. When in doubt whether a test would catch a regression, break that behavior in a scratch worktree and see whether the check fails. A criterion whose outcome requires a state reached through an operation needs a check through that operation. A canonical fixture counts when built by that operation, or when a passing conformance test ties it to the operation's output.

For each sponsor-judged `AC-n`, check its paired criterion and the judged state's reachability at the frozen head. Record the exact question, paired identifier and locator, and reproduction steps, then report `pending_sponsor`, never `pass`. Only a `pass` pair and reachable state permit `pending_sponsor`. Otherwise the sponsor row is `not_verified`, citing its paired criterion or unreachable state; re-verify it whenever its pair is re-verified.

In every visible feature criterion row, show the criterion's source issue as a
human-readable full `owner/repo#n` beside its local `AC-n`. Two source issues
may each have `AC-1`; keep them as separate visible rows with their respective
source issues. The result marker keeps ordinary local `AC-n` values and has no
new structured row identifier.

## Coverage check

For each check-decided criterion the spec marks new or changed, compare the mapped test cases and any old tests the spec names as superseded on baseline and frozen code:

For each criterion, report the four coverage kinds below with their dispositions and evidence in the visible result comment. Show its human-readable source issue `owner/repo#n` beside `AC-n` on every visible coverage row, including skipped rows. Include itemized test-case locators when several cases contribute to a row. A skipped row still states its reason. A repair or sponsor override names the affected criterion or coverage row and its source issue in prose and cites its current result comment; no structured coverage-row IDs are used.

| Kind | Run | Required result | Otherwise |
| --- | --- | --- | --- |
| `frozen-tests` | New or modified tests on frozen code | pass | `fail` |
| `old-code-tests` | Every new or modified test case mapped to the criterion, on old code | fails | `gap` |
| `superseded-frozen` | Old tests the spec names as superseded, on frozen code | at least one fails | `gap` |
| `superseded-old` | Those old tests on old code | pass | `not_verified` |

When a new or modified test suite cannot load on old code only because it imports modules the change adds, each of its mapped test cases counts as failing on old code; any other load failure on old code leaves the second row `not_verified`. A retained, unmodified old test is outside the second row. A purely new test has no old version; a purely additive criterion names no old test, so the last two rows are skipped. A deleted test is an old test without a new counterpart: its old version should fail on frozen code or deletion removed unchanged coverage (`gap`). If a run cannot happen, such as a journey on old code, mark that row `not_verified`. Report each applicable row and locator, including skips with their reason.

## Outcome and repair

`pass` requires every check-decided criterion `pass`, every sponsor row `pending_sponsor`, and every guard held. A later sponsor override does not change the verifier outcome. Exclude `pending_sponsor` rows from the overall outcome. Any `gap`, `not_verified`, `fail`, or broken guard yields overall `fail`; name each gap and suggest a test. Return an unrun or broken check to the verifier, without consuming review budget. A product defect returns to the retained builder and review. For a `gap` or coverage-row `not_verified`, automatically dispatch exactly one test-only fix round to the retained builder, without a sponsor checkpoint or review-budget charge. Compare the new head with the last clean reviewed head and require only tests addressing those rows in the delta. Freeze the new head and re-verify every affected criterion, including any paired sponsor row, without a separate review; the result comment identifies both the reviewed product head and the re-verified test-only head. A surviving gap, a coverage row a test cannot close, or a criterion-row `not_verified` keeps every pull request draft until an `orchestration-decision` marker records and is read back for a sponsor exception: amend the criterion, override with a reason, or stop. An override identifies the exact rows, heads, result URLs, and reason; the manager records it before merge-ready. Other test-only changes, documentation changes, and product-code changes return through the current-head review gate and a new freeze before verification. A documentation change re-verifies affected criteria and their paired sponsor rows after review; product-code changes receive the full applicable verification. Every new verification posts a new result; comments are never edited.
