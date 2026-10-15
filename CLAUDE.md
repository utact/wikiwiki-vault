# Employment domain ontology

This vault holds an ontology of the Korean employment domain served by 고용24, written as Markdown notes for Obsidian. The first domain is 이직 and 실업급여 under 고용보험법. Accuracy takes priority over coverage.

## Structure

The vault has three layers: raw sources that are never edited, the wiki that the LLM and scripts write, and the schema that defines the wiki.

| Path | Layer | Content |
| --- | --- | --- |
| `raw/` | Raw | Collected sources |
| `wiki/` | Wiki | Instance notes in one subfolder per class |
| `CLAUDE.md` | Schema | Operating rules |
| `ontology/schema.yaml` | Schema | RDF model in LinkML |
| `ontology/schema.md` | Schema | Document generated from `ontology/schema.yaml` |
| `ontology/release.yaml` | Schema | Reference date of the wiki |
| `ontology/verification.jsonl` | — | Verification ledger |
| `synthetic/` | — | Synthetic data |
| `scripts/` | — | Collection, generation and validation scripts |
| `tests/` | — | Fixture notes and tests for the scripts |
| `docs/` | — | Human-facing documents such as the roadmap |
| `index.md` | — | Notes by class |
| `log.md` | — | Operation log |

## Reference date

- `asOf` in `ontology/release.yaml` is the reference date (기준 시점) of the whole wiki.
- The current version of a law is the version in force on that date.
  - Decide it by comparing 시행일자 with the reference date, never by the API's 현행 or 연혁 label.
  - When one 시행일자 has several MSTs, use the one with the later 공포일자, then the later 공포번호.
- Changing the reference date is a `schema` operation.
  - Regenerate the statute notes and check the wiki afterwards.

## Raw sources

- Collect sources with scripts in `scripts/`.
  - Read API keys from `.env`.
  - Strip credential parameters such as `OC` from every stored URL and response.
- Use one folder per publisher.
  - `raw/law/`: 법제처, for both 법령 and 행정규칙
  - `raw/work24/`: 고용24 guides
  - `raw/stats/`: EIS, KOSIS and 공공데이터포털
- Give every raw note a basename that is unique in the vault: the source name, its version and the retrieval time in KST.
  - 법령: `raw/law/<법령명>/<법령명> <시행일자>-<MST> <YYYYMMDDTHHMM>.md`
  - 행정규칙: `raw/law/<행정규칙명>/<행정규칙명> <시행일자>-<행정규칙일련번호> <YYYYMMDDTHHMM>.md`
  - Keep the original response next to the note with the same basename and `.json`, and attachments with the same basename and their own extension.
  - Keep version lists as `<법령명> versions <YYYYMMDDTHHMM>.json`.
- Collect these versions of every law in scope.
  - The current version
  - Every scheduled version (시행예정)
  - Every earlier version that a 경과조치 still applies to someone who left before the change, such as 이직 before 2026-01-01 for 고용보험법 시행령 제68조
- Re-collect scheduled versions after each new promulgation, because a later amendment can change them.
- Keep 고용24 guide bodies local and out of Git.
  - 고용24 content without a 공공누리 mark needs prior consultation before redistribution.
  - Store the captured page as `raw/work24/<page name>/<page name> <YYYYMMDDTHHMM>.html`, which Git ignores.
  - Commit the raw note next to it, with the short quotations the wiki cites in `hasPart`, quoted under 저작권법 제28조.
- Fill every required property in the Raw sources section of `ontology/schema.md`, and the optional ones that apply.
- Record the terms of use in `license`.
  - Statutes: not protected works under 저작권법 제7조
  - Other sources: the 공공누리 type or the 공공데이터포털 terms of use
- Never edit a saved source.
  - On re-collection, write a new note with the new retrieval time.
  - Skip it if its `sha256` equals that of the previous retrieval.

## Synthetic data

- Keep synthetic data only in `synthetic/`.
  - Synthetic data stands in for non-public information.
  - Set `synthetic: true` in its frontmatter.
- Never cite or link synthetic notes from `wiki/` notes.
  - Synthetic notes may link `wiki/` notes.

## Statute notes

- Generate `LegalResource` and `LegalResourceSubdivision` notes from raw sources with a script.
  - The LLM never writes or edits statute text.
  - Write one note per law, 장, 절, 조, 별표, 별지 서식 and 부칙.
  - Generate the units that wiki notes or competency questions cite, their parent units, and the units those units cite.
- Name statute notes with the law name and the unit.
  - Examples: `고용보험법 제40조`, `고용보험법 별표 1`, `고용보험법 시행규칙 별지 제6호서식`, `고용보험법 부칙 제21473호`
- Put every collected version in the body under its own heading, and mark the current version in that heading.
- Prefix every block ID with the 시행일자 of its version, so that a block ID never changes meaning.
  - Whole text of a unit without 항 or 호: `^v20260918-t`
  - Lead text before the items (각 호 외의 부분): `^v20260918-lead`
  - 항: `^v20260918-p1`
  - 호: `^v20260918-p1-i1`, or `^v20260918-i1` when the unit has no 항
  - 가지 호 such as 제3호의2: `^v20260918-i3-2`
  - 목: `^v20260918-p1-i5-m1`, where 가 is 1 and 나 is 2
  - 비고 of a 별표: `^v20260918-note`
  - Articles of a 부칙 and their parts: `^v20260317-a3`, `^v20260317-a3-p1`
- Generate `cites` from the references in the text, and `basedOn` from explicit delegations such as "법 제45조제5항에 따라".
  - Resolve 법, 영 and 규칙 against the law family, 같은 조 against the current article, and short names defined in the text, such as 고용산재보험료징수법.

## Note format

- Name each file with its Korean preferred label (`skos:prefLabel`), unique in the vault.
  - If two notes would share a name, add the kind in parentheses, as in `이직 (사건)`.
  - File names may change, but an `identifier` never does.
- Choose the class by the kind of thing.
  - Benefits and procedures, such as 구직급여 and 실업의 신고: `PublicService`
  - Events, such as 이직: `LifeEvent` or `BusinessEvent`
  - Public bodies, such as 고용노동부: `PublicOrganisation`
  - Party types, such as 사업주 and 피보험자: `Concept` in the 고용보험 당사자 유형 scheme
  - Information that rules and conditions use, such as 이직일 and 기초일액: `InformationConcept`
  - Codes and lists of alternatives, such as 상실사유 구분코드 and 정당한 이직 사유: `Concept` in a `ConceptScheme`
  - Conditions and limits: `Criterion` and `Constraint`
  - Calculations and tables: `Rule`
  - Documents to submit, such as 이직확인서: `EvidenceType`
- Write frontmatter with schema properties only, in this order.
  1. `type`, `identifier`, `aliases` and `definition`
  2. Class properties, those of parent classes first, each group in the order of its table in `ontology/schema.md`
  3. `validFrom`, `validThrough` and `isReplacedBy`
  4. `source`, `status`, `reviewedBy` and `lastReviewed`
- Do not write `prefLabel`; `scripts/vault.py` takes it from the file name.
- Write every relation as wikilinks, only in the direction the schema defines, and read the inverse from backlinks.
  - A wikilink may point to a block, as in `"[[고용보험법 제45조#^v20260918-p5]]"`.
- Write a decision table as a header and rows of cells, which `scripts/vault.py` expands with positions.
- Change classes and properties only in `ontology/schema.yaml`.
  - Run `uv run python -X utf8 scripts/schema_doc.py` afterwards, and never edit `ontology/schema.md` by hand.
- Write the body in Korean.
  - Open with a definition paragraph.
  - Split the explanation under `##` headings.
  - Keep footnotes at the end.

The frontmatter of `wiki/PublicService/구직급여.md` looks like this.

```yaml
---
type: PublicService
identifier: job-seeking-benefit
definition: 이직한 피보험자가 수급 요건을 갖추어 실업의 인정을 받은 날에 지급하는 급여
hasCompetentAuthority: ["[[고용노동부]]"]
hasLegalResource: ["[[고용보험법 제40조]]", "[[고용보험법 제44조]]"]
source: ["[[고용보험법 제40조#^v20260918-p1]]", "[[고용보험법 제44조#^v20260918-p1]]"]
status: draft
---
```

The decision table of `wiki/Rule/소정급여일수 산정.md` starts like this.

```yaml
decisionTable:
  hitPolicy: UNIQUE
  input: ["[[이직일 현재 연령]]", "[[피보험기간]]"]
  output: ["[[소정급여일수]]"]
  rule:
    - ["< 50", "< 1", "120"]
    - ["< 50", "[1..3)", "150"]
```

## Citations

- Footnote every factual sentence with the block it rests on.
  - Statutes: a block of the statute note, labelled with the official citation, as in `[^1]: [[고용보험법 제40조#^v20260918-p1-i1|고용보험법 제40조제1항제1호]]`
  - 단서, 본문, 전단 and 후단: link the block, and name the part in the label
  - 고용24 guides: a quotation block of the raw note
- Quote statutory text verbatim inside double quotes, followed directly by its footnote.
  - Keep source text and interpretation in separate sentences.
- Every number, amount and date in a footnoted sentence must appear in a cited block, or come from a `Rule` that the sentence cites.
- Rank sources in this order.
  1. 법률
  2. 시행령
  3. 시행규칙
  4. 고시·행정규칙
  5. 고용24 official guides
  6. Statistics
- State a fact from the highest-ranked source.
  - When a lower-ranked source says otherwise, add a `> [!warning] 출처 불일치` callout that quotes both.
  - When sources of the same rank disagree, record both under a `> [!warning] 출처 충돌` callout and never pick one yourself.
- Write limits and conditions as FEEL `unaryTests` on a `Constraint` or `Criterion`.
  - Use `validFrom` and `validThrough` only for calendar validity.
  - Model a transitional provision (경과조치) as a `Criterion` on the date it depends on, such as 이직일, and link it with `appliesWhen`.
- Never state unconfirmed content as fact.
  - Leave it as a question in a `> [!question]` callout.

## Text checks

Scripts check quotes, numbers and hashes against this canonical text.

- The text of a statute block joins the 조문내용, 항내용, 호내용 and 목내용 of the block and all its children with newlines.
  - Keep amendment tags such as `<개정 2019.1.15>`.
- Compare texts after removing all whitespace, and change no other character.
  - "ㆍ" (U+318D) and "·" (U+00B7) stay different.
- Read numbers in these forms.
  - Digits with or without commas, such as 113,500
  - Korean units, such as 11만3500원 and 3천만원
  - Fractions and percentages, such as 100분의 60 and 70퍼센트
  - Dates, such as 2026-01-01, 2026.1.1. and 2026년 1월 1일
- The hash of a block is the SHA-256 of its canonical text.
- The `sha256` of a raw source is the SHA-256 of the canonical text of everything it contains, without metadata such as 조문이동이전.

## Review

Notes written by the LLM move through three statuses in order.

1. `draft`: created or edited by the LLM
   - Any edit, or any change in a cited block, returns a note to `draft`.
   - Log the reason in `log.md`.
2. `verified`: checked by a separate agent
   - The verifier did not write the note and works in a fresh context.
   - Run it as a subagent with model `opus` and effort `xhigh`.
   - Give it the note, the cited blocks and the notes that link to or from the note.
   - It compares every factual sentence with the cited blocks, checks schema conformance and looks for contradictions with the linked notes.
   - On any mismatch, the note stays `draft` and the required fixes go to `log.md`.
3. `reviewed`: approved by the human owner
   - Record `reviewedBy` and `lastReviewed`.
   - The LLM never sets `reviewed`, `reviewedBy` or `lastReviewed`.

- Statute notes generated by script start as `verified`, because the script checks them against the raw source.
- Append one line to `ontology/verification.jsonl` for every generated or verified note.
  - Key it by `identifier`.
  - Record the hash of the note without `status`, `reviewedBy` and `lastReviewed`, and the hashes of the cited blocks.
  - Record the generator and its commit, or the verifier's model, effort and session.
- Retired or superseded instances are never deleted.
  - Set `validThrough` and link the successor with `isReplacedBy`.

## Operations

### Ingest

Ingest reflects a source in the wiki.

1. Save the source to `raw/` with a script.
2. Regenerate the statute notes when the source is a statute.
3. Find related notes through `index.md`.
4. Create or edit notes.
   - If a needed class or property is missing, update the schema first.
5. Update `index.md` and `log.md`.

### Query

Query answers a question from the wiki.

- Link the notes that the answer rests on.
- If the wiki lacks the answer, say so and propose sources to collect.

### Lint

Lint checks the wiki for these problems.

- Links
  - Broken links and block references
  - Notes that nothing links to, except generated statute notes
- Schema
  - Notes that fail `uv run python -X utf8 scripts/vault.py check`, which validates them against LinkML and SHACL
  - `ontology/schema.md` out of date with `ontology/schema.yaml`
  - Duplicate file names, identifiers or aliases
- Sources
  - Factual sentences without a source
  - Quotes or numbers that do not match the cited block
  - Cited blocks whose hash differs from the one in the verification ledger
  - `verified` or `reviewed` notes without a matching ledger entry
  - Scheduled versions that come into force on or before the reference date
- Secrets
  - `.env` values in tracked files
- Synthetic data
  - Links from `wiki/` to `synthetic/`

## Log

- Append one entry per operation to `log.md`.
  - Never edit past entries.
- Write each heading as `## <date> <time> <operation>`.
  - Date and time are in KST.
  - The operation is one of `ingest`, `verify`, `review`, `lint` and `schema`.
- List the body fields in this order.
  1. `대상`
  2. `추가`, `수정`, `삭제`
  3. `내용`

An entry for ingesting 고용보험법 looks like this.

```markdown
## 2026-10-14 21:00 ingest

- 대상: 고용보험법
- 추가: [[고용보험법 제40조]]
- 수정: [[구직급여]]
- 내용: 현행 법령의 조문 반영
```

## Conventions

### Language

- Choose the language by reader.
  - `CLAUDE.md`: English
  - `ontology/schema.md`, `index.md` and `log.md`: English headings, Korean prose
  - `README.md`, `docs/` and vault notes in `wiki/`, `raw/` and `synthetic/`: Korean
- In Korean prose, write technical terms whose original is English in English.
  - Examples: ontology, schema, class, property, instance, wiki, vault, wikilink, backlink, frontmatter, callout, agent, context, hash
- In Korean prose, write loanwords listed in the Korean dictionary in Korean.
  - Examples: 파일, 폴더, 노트, 링크, 데이터, 스크립트
- Use the terms of the issuing authority.
  - Legal concepts: statutory terms, such as 이직 and 피보험자격
  - 법제처 data: 법제처 terms, such as 현행 법령 and 시행일자
- Coin no project-specific terms.
  - If no standard term exists, define the term where it first appears.

### Letter case

- Use capitals only where they carry meaning.
  - In English text, use sentence case for headings, list items and table cells.
  - In Korean prose, keep English common nouns lowercase.
  - Keep the spelling of proper nouns, such as Obsidian, Markdown and LLM Wiki, and of acronyms, such as API, IRI and RDF.
- Case identifiers by kind.
  - Classes: PascalCase
  - Properties: camelCase
  - Property values: lowercase
  - `identifier` values: kebab-case
- Keep the spelling of codes from external standards, such as `DAY`, `KRW` and `UNIQUE`.

### Korean prose

- Write short declarative sentences ending in "-다".
- Write one paragraph per line.
  - Never break a line mid-sentence.

### Markdown

- Section order
  - Put the overview first.
  - Order the remaining sections by operation, or so that each term is defined before use.
  - Put cross-cutting conventions last.
- Headings
  - Start a repository document with a single `#` heading.
  - Give vault notes no `#` heading, because the file name is the title.
  - Use one language for all headings of a document.
  - Never skip a heading level.
- Spacing
  - Put one blank line between headings, paragraphs, lists, tables and code blocks.
  - End every file with one newline.
- Lists
  - Number a list with `1.` only when order matters, and use `-` otherwise.
  - Keep each item to one point, and move details, cases and examples into nested items.
  - Make the items of one level all sentences or all phrases, and end only sentences with a period.
- Tables
  - Use a table only to compare items of one kind across attributes.
  - Write tables in compact style, with one space inside each pipe and `| --- |` delimiters.
  - Keep cells to phrases without periods, and put longer explanations in a paragraph below the table.
  - State the row order rule above the table when it is not obvious.
- Code
  - Use inline code for paths, file names, properties and values.
  - Put multi-line examples in fenced code blocks with a language, after a sentence that says what they show.
- Links
  - Link vault notes with wikilinks and external sources with `[name](URL)`.
- Emphasis
  - Use callouts for warnings and questions.
  - Do not use bold or italic.
- Checking
  - Check formatting with `npx markdownlint-cli2`, configured in `.markdownlint-cli2.jsonc`.

### Scripts

- Run Python with `uv run python -X utf8`.
  - Without UTF-8 mode, Python on Windows reads Korean files as CP949.
- Write files in UTF-8 with LF line endings.
- Keep every script check reproducible with the fixture notes in `tests/fixtures/`.

### Commits

- Write the subject as `type(scope): 한국어 요약`.
  - Type and scope are lowercase English.
  - The scope is optional.
- Write the body as a short `-` list after a blank line.
- Commit each unit of work on `main`.
