# Employment domain ontology

This vault holds an ontology of the Korean employment domain served by 고용24, written as Markdown notes for Obsidian. The first domain is 이직 and 실업급여 under 고용보험법. Accuracy takes priority over coverage.

## Structure

The vault has three layers: raw sources that are never edited, the wiki that the LLM writes and maintains, and the schema that defines the wiki.

| Path | Layer | Content |
| --- | --- | --- |
| `raw/` | Raw | Collected sources |
| `wiki/` | Wiki | Instance notes in one subfolder per class |
| `CLAUDE.md` | Schema | Operating rules |
| `ontology/schema.md` | Schema | Class and property definitions |
| `synthetic/` | — | Synthetic data |
| `scripts/` | — | Collection and validation scripts |
| `docs/` | — | Human-facing documents such as the roadmap |
| `index.md` | — | Notes by class |
| `log.md` | — | Operation log |

## Raw sources

- Collect sources with scripts in `scripts/`.
  - Read API keys from `.env`.
- Use one folder per publisher.
  - `raw/law/`: 법제처
  - `raw/work24/`: 고용24 guides
  - `raw/stats/`: EIS, KOSIS and 공공데이터포털
- Name files by source and date.
  - Statutes: `raw/law/<법령명>/<시행일자>.md`
  - Web pages: `raw/work24/<page name>/<retrieval date>.md`
  - Original API responses: a `.json` file with the same name, next to the note
- Fill every property in the Raw source properties table of `ontology/schema.md`.
- Record the terms of use in `license`.
  - Statutes: not protected works under 저작권법 제7조
  - Other sources: the 공공누리 type or the 공공데이터포털 terms of use
- Never edit a saved source.
  - On re-collection, write a new file.
  - Skip the new file if its `sha256` equals that of the previous file.

## Synthetic data

- Keep synthetic data only in `synthetic/`.
  - Synthetic data stands in for non-public information.
  - Set `synthetic: true` in its frontmatter.
- Never cite or link synthetic notes from `wiki/` notes.
  - Synthetic notes may link `wiki/` notes.

## Note format

- Name each file with its Korean preferred label (`skos:prefLabel`), unique in the vault.
  - Prefix article notes with the statute name, as in `고용보험법 제40조`.
  - File names may change, but an `identifier` never does.
- Write frontmatter with schema properties only.
  - Follow the order of the tables in `ontology/schema.md`.
  - Write each relation as an object property holding wikilinks.
  - Write a relation only in the direction the schema defines, and read the inverse from backlinks.
- Write the body in Korean.
  - Open with a definition paragraph.
  - Split the explanation under `##` headings.
  - Keep footnotes at the end.

The frontmatter of `wiki/PublicService/구직급여.md` looks like this.

```yaml
---
type: PublicService
identifier: job-seeking-benefit
aliases: [실업급여]
definition: 피보험자가 실업 상태에서 재취업활동을 하는 동안 지급하는 급여
hasCompetentAuthority: ["[[고용노동부]]"]
hasLegalResource: ["[[고용보험법 제40조]]"]
source: ["[[고용보험법 제40조]]"]
status: draft
---
```

## Citations

- Footnote every factual sentence with its source.
  - Statutes: a paragraph of the article note, as in `[[고용보험법 제40조#제1항]]`
  - 고용24 guides: the raw note
- Quote statutory text verbatim.
  - Keep source text and interpretation in separate sentences.
- Rank sources in this order.
  1. 법률
  2. 시행령
  3. 시행규칙
  4. 고시·행정규칙
  5. 고용24 official guides
  6. Statistics
- When sources disagree, record both under a `> [!warning] 출처 충돌` callout.
  - Never pick one yourself.
- Give amounts, periods and rates a reference date.
  - Give values that can change `validFrom` and `validThrough`.
- Never state unconfirmed content as fact.
  - Leave it as a question in a `> [!question]` callout.

## Review

Notes move through three statuses in order.

1. `draft`: created or edited by the LLM
   - Any edit, or any change in the cited source, returns a note to `draft`.
   - Log the reason in `log.md`.
2. `verified`: checked by a separate agent
   - The verifier did not write the note and works in a fresh context.
   - Run it as a subagent with model `opus` and effort `xhigh`.
   - It compares every factual sentence with the cited source.
   - It confirms that quotes match the source character for character.
   - It checks schema conformance.
   - On any mismatch, the note stays `draft` and the required fixes go to `log.md`.
3. `reviewed`: approved by the human owner
   - Record `reviewedBy` and `lastReviewed`.
   - The LLM never sets `reviewed`.

Retired or superseded instances are never deleted. Set `status: deprecated` and link the successor with `isReplacedBy`.

## Operations

### Ingest

Ingest reflects a source in the wiki.

1. Save the source to `raw/` with a script.
2. Find related notes through `index.md`.
3. Create or edit notes.
   - If a needed class or property is missing, update the schema first.
4. Update `index.md` and `log.md`.

### Query

Query answers a question from the wiki.

- Link the notes that the answer rests on.
- If the wiki lacks the answer, say so and propose sources to collect.

### Lint

Lint checks the wiki for these problems.

- Links
  - Broken links
  - Notes that nothing links to
- Schema
  - `type` values or properties missing from the schema
  - Missing required properties
- Sources
  - Factual sentences without a source
  - Changed `sha256` values in raw sources, and the notes they affect
- Synthetic data
  - Links from `wiki/` to `synthetic/`
- Content
  - Contradictions between notes

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

### Commits

- Write the subject as `type(scope): 한국어 요약`.
  - Type and scope are lowercase English.
  - The scope is optional.
- Write the body as a short `-` list after a blank line.
- Commit each unit of work on `main`.
