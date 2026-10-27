# Employment domain ontology

This vault holds an ontology of the Korean employment domain served by 고용24, written as Markdown notes for Obsidian. The first domain is 이직 and 실업급여 under 고용보험법. Accuracy takes priority over coverage.

## Structure

The vault has three layers: raw sources that are never edited, the wiki that the LLM and scripts write, and the schema that defines the wiki.

| Path | Layer | Content |
| --- | --- | --- |
| `raw/` | Raw | Collected sources |
| `wiki/` | Wiki | Instance notes in one subfolder per class |
| `CLAUDE.md` | Schema | Operating rules |
| `.claude/settings.json` | — | Claude Code hooks that enforce the rules |
| `ontology/schema.yaml` | Schema | RDF model in LinkML |
| `ontology/schema.md` | Schema | Document generated from `ontology/schema.yaml` |
| `ontology/release.yaml` | Schema | Reference date, transitional window and jurisdiction of the wiki |
| `ontology/shapes/` | Schema | Official SHACL shapes of CPSV-AP and CCCEV |
| `ontology/verification.jsonl` | — | Verification ledger |
| `ontology/cq/` | — | SPARQL queries of the competency questions |
| `views/` | — | Obsidian canvases and bases that show the wiki |
| `.obsidian/` | — | Obsidian settings, without the workspace files |
| `synthetic/` | — | Synthetic data |
| `scripts/` | — | Collection, generation and validation scripts |
| `tests/` | — | Fixture notes and tests for the scripts |
| `.cache/` | — | Local cache of uncited raw versions, ignored by Git |
| `docs/` | — | Human-facing documents such as the roadmap and the decision record |
| `index.md` | — | Notes by class |
| `log.md` | — | Operation log |
| `TODO.md` | — | Current and next tasks of the human owner and the agent |

## Reference date

- `asOf` in `ontology/release.yaml` is the reference date (기준 시점) of the whole wiki.
- The current version of a law is the version in force on that date.
  - Decide it by comparing 시행일자 with the reference date, never by the API's 현행 or 연혁 label.
  - When one 시행일자 has several MSTs, use the one with the later 공포일자, then the later 공포번호.
- Changing the reference date is a `schema` operation.
  - Regenerate the statute notes and check the wiki afterwards.

## Raw sources

- Collect sources with `uv run python -X utf8 scripts/collect.py`, which reads the source list in `scripts/sources.yaml`.
  - Read API keys from `.env`.
  - Strip credential parameters such as `OC` from every stored URL and response.
  - Check the result with `uv run python -X utf8 scripts/check_raw.py` before committing.
  - It needs the local cache that `scripts/collect.py` writes, because it compares every version in the transitional window.
  - It explains each changed unit by an amendment tag dated as a promulgation of that version, by 조문변경여부, or as the new 부칙 of that version.
  - It explains each removed unit by 조문이동이전, or by an earlier version in which the whole unit was a deletion, such as `제22조 삭제 <2006.12.28>`.
  - It works per unit: one matching tag explains every change in the unit.
- Use one folder per publisher.
  - `raw/law/`: 법제처, for both 법령 and 행정규칙
  - `raw/work24/`: 고용24 guides
  - `raw/stats/`: EIS, KOSIS and 공공데이터포털
- Give every raw note a basename that is unique in the vault: the source name, its version and the retrieval time in KST.
  - 법령: `raw/law/<법령명>/<법령명> <시행일자>-<MST> <YYYYMMDDTHHMM>.md`
  - 행정규칙: `raw/law/<행정규칙명>/<행정규칙명> <시행일자>-<행정규칙일련번호> <YYYYMMDDTHHMM>.md`
  - Keep the original response next to the note with the same basename and `.json`.
  - Keep attachments with the same basename followed by `-1`, `-2` and so on, with their own extension: first the 첨부파일 of a 고시 in the order of the response, then the image files the response links to as `<img src>` or `<img id>`, in order of first appearance.
  - Store the image files because some text exists only in them, such as the formulas of 고용산재보험료징수법 시행령 제18조의2 and the amount in `2020년 적용 최저임금 고시`.
  - Keep version lists as `<법령명> versions <YYYYMMDDTHHMM>.json`.
  - 위임조문 data: `raw/law/<법령명> 위임조문/<법령명> 위임조문 <시행일자>-<MST> <YYYYMMDDTHHMM>.md`, in its own folder so that it stays apart from the versions of the law
  - 법령해석례: `raw/law/법령해석례/법령해석례 <안건번호> <YYYYMMDDTHHMM>.md`, with the response next to it as `.json`
- Collect these versions of every 법령 and 행정규칙 in scope.
  - The current version
  - Every scheduled version (시행예정)
  - Every earlier version in force during the transitional window, so that text kept by a 경과조치 is at hand, such as 고용보험법 시행령 제68조 before 2026-01-01
  - Leave out proposals published under the same 행정규칙ID, such as `2027년 적용 최저임금안 고시`.
- Collect the 법령해석례 of 법제처 listed under `interpretations` in `scripts/sources.yaml` with `scripts/collect.py interpretations`.
  - List one when it interprets a provision that the wiki states or a question callout asks about, such as 법령해석례 26-0321 on counting a period of days under 행정기본법 제6조제1항 and 민법.
  - Quote its 질의요지, 회답 or 이유 with `scripts/collect.py quote "법령해석례 <안건번호>" <section> "<text>"`, as for a 고용24 guide.
- Collect the 위임조문 data of the current version of every 법률 and 시행령 in scope.
  - It names each provision that delegates to a 시행령 or 시행규칙 and the article that receives it.
  - 법제처 keeps it for its 현행 version only, so collect it again when a new version comes into force. `scripts/collect.py` stores no response of another version, and `scripts/check_raw.py` fails when the current version lacks it.
- The transitional window is `transitionalWindow` in `ontology/release.yaml`, counted back from the reference date.
  - It starts with the version in force on its first day.
  - It is the longest time a person can still receive 구직급여 after 이직: 4 years (고용보험법 제48조제2항) plus 2 years of 훈련연장급여 (시행령 제72조), 60 days of 개별연장급여 (법 제52조제2항) and 60 days of 특별연장급여 (법 제53조제1항), which are paid one after another (법 제55조) and lengthen the 수급기간 (법 제54조제1항).
  - Recompute it when any of those provisions changes.
  - It covers entitlement and payment. Recovery under 법 제62조 can concern 부정수급 before the window, because the right to recover lasts 3 years (법 제107조제1항제3호) and can be interrupted (같은 조 제2항).
  - For such cases, cite the 경과조치 and leave the earlier text as a question until a competency question needs it.
- List the 부칙 articles that govern the window with `uv run python -X utf8 scripts/transitional.py`.
  - It reads the 부칙 of the current and scheduled versions, whose titles contain 경과조치, 적용례, 특례 or 유효기간, of every promulgation with a 시행일자 on or after the first day of the window.
  - It shows the units each article names: articles, 항, 호, 별표, 별지 서식 and 같은 조, but not the articles of the 부칙 itself, such as "부칙 제4조부터 제7조까지".
  - List those that name no unit for review in `log.md`.
- Walk back the version list as far as needed to date the text of each generated unit, as described in Statute notes.
  - Commit only the versions that the wiki cites or that are current or scheduled.
  - Keep the others in the local cache, `.cache/law/` and `.cache/admrul/`, which Git ignores.
  - When a wiki note cites an earlier version that only the cache holds, `scripts/collect.py cited` writes its raw note.
- Re-collect scheduled versions after each new promulgation, because a later amendment can change them.
- Keep 고용24 guide bodies local and out of Git.
  - 고용24 content without a 공공누리 mark needs prior consultation before redistribution.
  - Store the captured page as `raw/work24/<page name>/<page name> <YYYYMMDDTHHMM>.html`, which Git ignores.
  - Commit the raw note next to it, with the short quotations the wiki cites in `hasPart`, quoted under 저작권법 제28조.
  - Number the quotation blocks `^q1`, `^q2` in the order of `hasPart`, and cite them as `[[<raw note>#^q1]]`.
  - Add a quotation with `uv run python -X utf8 scripts/collect.py quote "<page name>" <section> "<text>"`, which checks it against the section of the stored page and appends it to the latest raw note. `scripts/check_raw.py` checks the numbering, blocks, hashes and text of every quotation, of 고용24 guides and 법령해석례 alike.
- Fill every required property in the Raw sources section of `ontology/schema.md`, and the optional ones that apply.
- Set `sha256` to the SHA-256 of the stored response file followed by its attachments in their order.
  - The latest retrieval of each version stores every attachment. An earlier retrieval keeps the files it stored, such as the 법령 retrievals of 2026-10-15 13:37 made before image files were collected.
  - This hash does not depend on how scripts read the text, so a change in the reading rules leaves raw notes as they are.
  - Any change in a response makes a new raw note, even in a field outside the text, such as a contact number.
  - For a 고용24 guide, whose page stays out of Git, use the text of its body area without whitespace, section by section. This hash changes when the reading of the page changes.
- Record the terms of use in `license`.
  - Statutes: not protected works under 저작권법 제7조
  - Other sources: the 공공누리 type or the 공공데이터포털 terms of use, such as 이용허락범위 제한 없음 for the 법령해석 data of 법제처
- Never edit a saved source.
  - The only allowed edits are appending a quotation to `hasPart` of a 고용24 or 법령해석례 raw note, and recomputing `sha256` in every raw note in one `schema` operation when its definition changes.
  - On re-collection, write a new note with the new retrieval time.
  - Skip it if its `sha256` equals that of the previous retrieval.

## Synthetic data

- Keep synthetic data only in `synthetic/`.
  - Synthetic data stands in for non-public information.
  - Set `synthetic: true` in its frontmatter.
- Never cite or link synthetic notes from `wiki/` notes.
  - Synthetic notes may link `wiki/` notes.

## Statute notes

- Generate `LegalResource` and `LegalResourceSubdivision` notes from raw sources with `uv run python -X utf8 scripts/statutes.py`.
  - The LLM never writes or edits statute text.
  - Write one note per law, 장, 절, 조, 별표, 별지 서식 and 부칙.
  - Generate the units that wiki notes or competency questions cite, their parent units, and the units those units cite directly.
  - Keep generating every unit that already has a statute note, so that no note goes stale.
  - Commit `scripts/` first: `statutes.py` writes notes only from a committed generator, so that the ledger names it.
  - It prints `REVIEW` lines for dates that fail the check below, moved or reused article numbers within the versions a note shows, cited versions without a raw note, references not counted as delegations, delegations the 위임조문 data does not list, units kept only because their note exists, images without text, glyphs lost as "?" and form text that stands side by side without frames. Record them in `log.md`.
  - `--check` lists the notes that differ from a fresh generation or from the ledger. It changes and fetches nothing, and stops when the cache lacks a version it needs.
  - `--versions "<unit>"` lists the versions of a unit in the transitional window with their block IDs, for citing an earlier version.
- Statute notes follow article numbers.
  - `statutes.py` does not yet carry an identifier across a move, or keep the earlier article of a reused number apart.
  - A move or reuse dated on or before the earliest version of a note leaves the note one article, as 정부조직법 제41조 from 2025-10-01, so it is not listed.
  - When a scheduled version moves an article that has a note, change the generator in a `schema` operation before that version becomes current.
  - Cite no earlier version of a reused number until then.
- List laws that the wiki cites only for a definition or a general rule, such as 정부조직법 for 고용노동부 and 민법 for the computation of periods, under `references` in `scripts/sources.yaml`.
  - Collect their current and scheduled versions only.
- Give statute notes these identifiers.
  - Law: `law-<법령ID>`, and for a series of 고시 under one 행정규칙ID: `admrul-<행정규칙ID>`
  - Units: the law's identifier followed by `-art-40`, `-art-10-2`, `-ch-4`, `-ch-5-2`, `-ch-4-sec-2`, `-part-1-ch-6` for a 장 of a 편, `-annex-1-2`, `-form-6` or `-sup-<공포일자>-<공포번호>`
- Write a series of 고시 such as the 적용 최저임금 고시 as one `LegalResource` named after the current 고시, with each year's 고시 as a version and its text as the block `^v20260101-t`.
  - When the response carries the 개정문 of a 고시, give it the block `^v20221229-preamble`, because it names the provisions the 고시 rests on, as 고용보험법 제2조제5호 단서 for 고시 제2022-116호.
- Write a 행정규칙 that 법제처 gives as a list of articles, such as a 훈령 or 예규, as a `LegalResource` that links its versions, with notes for the articles that wiki notes cite and the 장 that hold them.
  - Units: `admrul-<행정규칙ID>-art-12` and `admrul-<행정규칙ID>-ch-2`, named as in `실업인정 및 재취업지원규정 제12조`
  - 법제처 gives each article as one string, so each version of a unit is one block, `^v20260901-t`. A citation names its 항 and 호 in the label.
  - Date the versions as for a law, with the 발령일자, 발령번호 and 행정규칙일련번호 of the version found. A unit is listed for review when an earlier version has no articles in 조문내용.
  - These notes carry no `cites` or `basedOn` yet.
- Name statute notes with the law name and the unit.
  - Examples: `고용보험법 제40조`, `고용보험법 별표 1`, `고용보험법 시행규칙 별지 제6호서식`, `고용보험법 부칙 제21473호`
  - When two 부칙 of a law share a 공포번호, add the 공포일자 in parentheses, as in `고용보험법 시행규칙 부칙 제263호 (2019. 9. 30.)` and `고용보험법 시행규칙 부칙 제263호 (2019. 10. 15.)`.
- Give a unit a new version only when its version text, defined in Text checks, changes.
  - A change of the amendment tags alone also makes a new version, because the tag records an amendment, as in 32 of 1,537 unit changes up to 2026-10-15.
  - Date the version by the 시행일자 of the earliest law version in the latest unbroken run of versions that have this text of the unit. This is the version's `firstDateEntryInForce`.
  - Check the date against the text: a promulgation of the law version found must have the date of the latest amendment tag of the unit, such as `<개정 2021.1.5>`.
  - Record that promulgation's 공포일자, 공포번호 and MST in the version.
  - A unit without amendment tags, such as a 장 heading, takes the promulgation only when it is the single one in force from that date and is a 제정 or 전부개정.
  - List the unit for review when no promulgation qualifies, as with the tag `2021.7.2` of 고용보험법 시행규칙 제87조 in the version of the promulgation dated 2021-07-01, and leave out the 공포일자 and 공포번호.
  - End each version the day before the first later law version whose text of the unit differs, or that lacks the unit. This is its `dateNoLongerInForce`.
  - A 부칙 gets versions like any other unit, because a later act can amend it, as 대통령령 제35100호 deleted 제18조 of 고용보험법 시행령 부칙 제22603호 from 2025-01-01.
- Put the current, scheduled and cited versions of the unit in the body, each under its own heading, and mark the current one.
  - Never remove a version that a note cites.
- Prefix every block ID with the date of its version, so that a block ID never changes meaning.
  - Whole text of a unit without 항 or 호: `^v20260918-t`
  - Lead text before the items (각 호 외의 부분): `^v20260918-lead`
  - 항: `^v20260918-p1`
  - 호: `^v20260918-p1-i1`, or `^v20260918-i1` when the unit has no 항
  - 가지 호 such as 제3호의2: `^v20260918-i3-2`
  - 목: `^v20260918-p1-i5-m1`, where 가 is 1 and 나 is 2
  - 비고 of a 별표: `^v20260918-remarks`
  - 개정문 of a 고시: `^v20221229-preamble`
  - Articles of a 부칙 and their parts: `^v20260317-a3`, `^v20260317-a3-p1`, where `a3` holds only the heading when the article has 항
  - 별지 서식: only the whole text, `^v20260918-t`, with its parts cited by quotation
- The text of a block includes the text of its children, such as the 호 of a 항, for quotes, numbers and hashes.
- Show image files in place of the `<img>` elements of statute text, as embeds of the attachments of the raw note.
  - Keep the table text an image carries after the embed, inside an Obsidian comment (`%%<img>…</img>%%`), so that quotes and numbers can be checked against it.
- Generate `cites` from the references in the text, and `basedOn` from the 위임조문 data of 법제처.
  - The data decides the delegations from a 법률 or 시행령 to an article of the current version of a lower law, as 법 제42조제3항 and 제43조제4항 for 시행규칙 제82조의2.
  - Add the raw note of the data to `source` of each note that takes `basedOn` from it.
  - Read from the text, by the rules below, the delegations the data does not cover: those applied by 준용, as 법 제15조제3항 in "법 제77조의10제1항에서 준용하는 법 제15조제3항에 따라", and those to 별표, 부칙 and units outside the current version.
  - When the text reads a delegation that the data does not list, write no `basedOn` and list it for review, as 시행령 제86조 on 법 제64조제1항.
  - Resolve 법, 영 and 규칙 against the law family, and short names defined in the text, such as 고용산재보험료징수법.
  - Resolve 같은 조, 같은 항 and 같은 호 against the article, 항 and 호 cited just before in the line, or the current article when none is.
  - Resolve 같은 법, 같은 영 and 같은 규칙 against the law named just before in the line, by any 「…」 name, and drop the reference when that law is out of scope, as 같은 법 제49조 after 「부가가치세법」 제32조.
  - Drop a 같은 조, 같은 항 or 같은 호 that follows a reference to a law out of scope.
  - A reference after 부터, 까지, ㆍ, 및, 또는 or a comma belongs to the law of the reference before it, as 제132조 in "「형법」 제129조부터 제132조까지".
  - So does an article that opens a parenthesis right after a reference, as 제77조의5제3항 in "법 제87조(제77조의5제3항ㆍ제4항 및 제77조의10제3항ㆍ제4항에서 준용하는 경우를 포함한다)".
  - So does an article inside a phrase quoted from another provision, as 제47조제1항 in `법 제68조제2항 본문에서 "제47조제1항에 따른 신고의무의 불이행 … 사유"란`, and such a reference is never a delegation.
  - A bare 항, 호 or 목 after such a word continues the article before it, as 제3항 in "제11조제2항ㆍ제3항" and 다목 in "제58조제1호나목 및 다목".
  - A range such as "제56조부터 제58조까지" or "제1항부터 제3항까지" cites every unit in it.
  - Title lines, 조문참고자료 and the headings of 부칙 articles are not references, because they name the unit itself or its history, as "제44조에서 이동".
  - Read references in 별표 and 별지 서식 with their wrapped lines joined, because a law name can wrap, as "「고용보" and "험법 시행규칙」".
  - Skip the 부칙 articles titled 다른 법률의 개정 or 다른 법령의 개정, because their references belong to another law.
  - Link the 개정규정 that a 부칙 names to the version of the 부칙's promulgation, as 제45조제1항 in 고용보험법 부칙 제21473호 to the version of 2028-01-01.
  - When the note of the cited unit does not show that version, link the unit and list it for review.
  - Count a reference in the text as a delegation only when it is followed by 에 따라, 에 따른 or 에서, stands outside parentheses, opens its 항 or article, and the cited provision delegates to the citing kind of law.
    - A reference in a 별지 서식 never counts, because the article that prescribes the 서식 receives the delegation.
    - A reference opens its provision when nothing precedes it there, or only a topic or a clause of 불구하고, as in "사업주나 하수급인은 법 제15조에 따라" and "제2항에도 불구하고 법 제45조제5항에 따라". Every member of a list such as "법 제21조제1항 및 제2항에 따라" opens it when the first one does.
    - One inside a 호 or in the middle of a sentence describes, as in "법 제48조에 따른 수급기간이 종료된 경우", and so does "에 따라" before a participle, as in "법 제75조에 따라 지급된".
    - This misses real delegations in the middle of a sentence, such as 시행규칙 제82조의2 on 법 제42조제3항, which the 위임조문 data supplies. Where the data does not apply, they are listed for review.
    - The cited provision is the text of the cited block without its children, the part the reference names, such as 단서 or 후단, or any 항 or 호 of a whole article.
    - It delegates when a sentence of it says "대통령령으로 정하는" for a 시행령 or "고용노동부령으로 정하는" for a 시행규칙, in any form such as 정한다, or when the reference quotes such a phrase of it, as in "법 제61조제2항 본문에서 "대통령령으로 정하는 사유"란".
    - After 에 따른 or 에서, the word that follows names the matter, and its first two syllables must appear in that sentence, as 추가 for "법 제62조제2항 본문에 따른 추가징수액". "법 제40조제2항제1호에 따른 기준기간" is not a delegation, because the delegating sentence of that 호 is about a 사유. A word of one syllable, such as 월, names no matter. Such references are listed for review.
    - A reference in parentheses qualifies the provision, as "(법 제63조에 따라 상병급여를 받은 경우의 질병이나 부상은 제외한다)".
  - Link only units that have statute notes, and a block only when the cited version declares it.

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
  - 단서, 본문, 전단 and 후단: link the block, and name the part in the label, only when the block has it
  - Items of a 별표 or 서식: link the block, and name the item in the label, as in `고용보험법 시행령 별표 2 제1호나목`
  - 항 and 호 of a 행정규칙 article: link the block, and name them in the label, as in `실업인정 및 재취업지원규정 제12조제2항제1호`
  - 법령해석례 and 고용24 guides: a quotation block of the raw note, labelled with the name of the source, as in `[^2]: [[법령해석례 26-0321 20261019T2045#^q1|법제처 법령해석례 26-0321]]`
  - Decisions of the human owner: a block of `docs/decisions.md`, next to the blocks the reading rests on, as described in Decisions
  - A footnote to a whole raw note rests only on its frontmatter and the basic information of its response, such as 시행일자 and 공포번호.
- Quote statutory text verbatim inside “ ” (U+201C and U+201D), followed directly by its footnote.
  - Statute text itself uses ASCII double quotes, as in `[이하 "기초일액(基礎日額)"이라 한다]`.
  - Use no other quotation marks in prose, such as ‘ ’ or ASCII double quotes.
  - Keep source text and interpretation in separate sentences.
- Write numbers in Arabic numerals, so that they can be checked: 2배, not 두 배, and 10일, not 열흘. Keep the words only where the cited block writes them so, as 두 번 이상 in some statutes.
- Every number, amount and date in a footnoted sentence must appear in a cited block, with the same unit.
  - Numbers inside citations, such as 제45조제5항, 별표 1 and 부칙 제21473호, are exempt.
  - Numbers inside the names of wiki notes, such as 이직 전 1일 소정근로시간, are exempt, because the note they name carries its own sources.
  - Names that contain digits, such as 고용24, are not numbers.
  - Give a calculated number a footnote that links its `Rule` and states the calculation in inline code, such as `113500 * 60 / 100`; the checker evaluates it.
  - The operands of a calculation must appear in a cited block, as a number or as a ratio such as 100분의 60 for `60 / 100`.
  - Mark a calculation on example inputs with 예시 in its footnote, as in `` [^3]: [[최저기초일액 산정]] 예시 `8 * 10320` ``. Its operands may then appear in the sentence instead.
  - Numbers in the labels of wikilinks, as in `[[기초일액|11만3500원]]`, count as part of the sentence, except the 공포일자 or 시행일자 of the statute note the link names, as in `[[고용보험법 시행령 부칙 제35934호|부칙 제35934호(2025. 12. 23.)]]`.
  - The 시행일 of the version of a cited statute block counts as part of the block, as 2020-08-28 for `[[고용보험법 제62조#^v20200828-p2]]`, because a 부칙 sometimes states it only as a time after 공포, such as 공포 후 1년이 경과한 날.
- Numbers and dates in `definition`, `unaryTests`, decision table cells and `literalExpression` must appear in the blocks of `source` or `isDerivedFrom`.
  - The 시행일 of the version of such a block counts, as in a footnoted sentence.
  - A number in a test or cell carries the unit of its concept's `unitCode` or `currency`, such as 일 for `DAY` and 원 for `KRW`, and a part of a duration its own unit, such as 개월 for `M`.
  - An operand of `*` or `/` carries no unit, because it states a ratio, as 60 and 100 in `기초일액 * 60 / 100`.
  - 0 and 1 in FEEL are exempt, because they often encode structure, as `duration("P1M")` for 다음 달.
- Rank sources in this order.
  1. 법률
  2. 시행령
  3. 시행규칙
  4. 고시·행정규칙
  5. 법령해석례 of 법제처, which interpret the statutes above without binding as they do
  6. 고용24 official guides
  7. Statistics
- State a fact from the highest-ranked source.
  - When a lower-ranked source says otherwise, add a `> [!warning] 출처 불일치` callout that quotes both.
  - When sources of the same rank disagree, record both under a `> [!warning] 출처 충돌` callout and never pick one yourself.
- Write limits and conditions as FEEL `unaryTests` on a `Constraint` or `Criterion`.
  - Use `validFrom` and `validThrough` only for calendar validity.
  - Model a transitional provision (경과조치) as a `Criterion` on the date it depends on, such as 이직일, and link it with `appliesWhen`.
  - A note with `appliesWhen` may cite a version that is not in force on the reference date, when the version's period meets the dates in which all its criteria hold.
  - A criterion on a date may cite such a version when the version's period meets the dates its own test admits, as 2023-07-01 이후 수급자격 인정 신청 cites the 2023-07-01 version of 고용보험법 제40조.
  - Criteria that test no date leave such a citation unchecked, so lint reports it.
- State a provision with its 단서 and exceptions, or name the ones a note leaves out.
  - Leave out a case that a rule, constraint or criterion does not cover through a criterion in `appliesWhen`, as 기초일액 산정 does for 고용보험법 제45조제1항 단서.
  - Leave out the same way a case in which two provisions can apply and neither prevails, as 최저기초일액이 상한액 이하 does for 고용보험법 제45조제4항 and 제5항.
- Describe an item that counts only under the condition of the item above it together with that condition, as each 목 of 고용보험법 시행규칙 별표 2 제5호.
- Never state unconfirmed content as fact.
  - Leave it as a question in a `> [!question]` callout, each line ending in "?".

## Text checks

Scripts check quotes, numbers and hashes against texts derived from the canonical text of a source.

- Take the canonical text of each kind of source from these fields.
  - 조문 block: 조문내용, 항내용, 호내용 and 목내용 of the block and all its children, then 조문참고자료 such as `[본조신설 2020.6.9]`, joined with newlines
  - 별표 and 별지 서식: 별표내용
  - 부칙: 부칙내용
  - 고시: 조문내용, then the text extracted from the PDF attachment named after the 고시, because some years keep the text only there
  - 개정문 of a 고시: 개정문내용
  - 고용24 guide: the text of the body area, section by section as its table of contents lists them
- Keep amendment tags such as `<개정 2019.1.15>`.
- Read the text in cell order before any comparison.
  - Count display columns with ASCII 1 wide and every other character 2 wide, and a "?" before a wide character 2 wide, at the start of a line or after another wide character, because it stands for a lost glyph such as an arrow.
  - Split each line at box-drawing characters (U+2500 to U+257F), and leave out runs of spaces.
  - Runs on adjacent lines belong to one cell when they start within 2 columns of each other and share at least 2 columns, or 1 when a run is narrower than 2.
  - A cell then keeps its wrapped lines whatever the widths of the other columns, and text that runs past a border does not join the next column.
  - Lines with box-drawing characters and lines without them never join.
  - Put cells in the order of their first line, then of their column.
  - Inside `<img>` elements, whose table text comes without line breaks, break the line where a line end meets a line start, such as `││`.
  - Text without box-drawing characters stays one cell per paragraph.
- Compare quotes against the comparison text: the text in cell order without whitespace.
  - Wrapped lines of 별표 and spaces inserted by PDF extraction then stop mattering.
  - Table text inside `<img>` elements stays without the tags, because some tables exist only there, such as 고용보험법 시행규칙 제105조.
  - "ㆍ" (U+318D) and "·" (U+00B7) stay different.
- Compare numbers as whole tokens of the text in cell order, with a break between cells.
  - Then 100분의 30 does not match inside 100분의 300, and the cells 100분의 100 and 100분의 150 stay two numbers.
  - Join the wrapped lines of a table cell, and every line of 별표, 별지 서식 and PDF text, without a break, because they wrap in the middle of words, as `210` and `만원` in 고용보험법 시행규칙 별지 제52호서식.
  - Keep the lines of 조문 fields apart, because each is a 항, 호 or 목.
  - In statute text, leave out the numbers of bracketed notes, such as `<개정 2019.1.15>` and `[본조신설 2020.6.9]`. In wiki notes, check them.
- Read numbers in these forms.
  - Digits with or without commas, such as 113,500
  - Korean units, such as 11만3500원 and 3천만원
  - Fractions and percentages, such as 100분의 60, 1천분의 5 and 70퍼센트
  - Dates, such as 2026-01-01, 2026.1.1. and 2026년 1월 1일
- Keep the unit after a number, such as 원, 일, 개월, 세 or 달러, so that 113,500원 and 113,500달러 differ.
- Decide versions and hashes of units on the version text: the comparison text without `<img>` elements and the text inside them.
  - It also leaves out the "■ 고용보험법 시행규칙" header that 법제처 added before [별표 1의2] and other tables in 2019, a display format.
  - Some versions of a 법제처 response leave out the text inside `<img>` elements that other versions carry, such as 고용보험법 시행규칙 제105조 in the version of 2024-07-01.
  - An amendment of such a table shows in the amendment tag of its unit, as the table of 제105조제1항 did in `<개정 2020.8.28, 2026.7.1>`.
  - `scripts/check_raw.py` fails when the text inside images differs from the last version that carried it while the version text does not, whatever 조문변경여부 says.
  - It fails when image files change while the version text does not and no image text shows the same content.
  - It fails when the lines restored from an image lack a frame at either end or differ in width by more than 2 columns.
  - It lists current units with images that carry no text, such as the formulas of 고용산재보험료징수법 시행령 제18조의2, for review.
- The hash of a block is the SHA-256 of its version text, children included.

## RDF export

`uv run python -X utf8 scripts/vault.py export OUT.ttl` writes the wiki as RDF after the checks of `vault.py check` pass.

- Each declared block becomes a version-independent `LegalResourceSubdivision`, such as `law-001761-art-45-p5`, with one `LegalExpression` per version, such as `law-001761-art-45-v20210701-p5`.
  - A version of a block carries the dates of its unit's version, but not the 공포일자, 공포번호 or MST, which belong to the act.
- A block link in `source` names the version of the block, and one to a whole-text block `^v…-t` the version of the note's own unit.
- A block link in `cites`, `basedOn`, `isDerivedFrom`, `implements` or `hasLegalResource` names the block itself, or the unit for a whole-text block, because ELI, CPSV-AP and CCCEV give these properties works as range.
- The export adds what the standards expect and the notes leave implicit.
  - `dct:title` and `dct:description` from the note name and `definition`, for the classes that CPSV-AP and CCCEV describe
  - The language tag `ko` on the names and descriptions that the official shapes require as `rdf:langString`, and only there, because CCCEV requires `xsd:string` for some of them
  - `dct:spatial` of every public organisation, from `jurisdiction` in `ontology/release.yaml`
  - The values of the schema's enumerations as SKOS concepts in concept schemes
- The checks also validate the export against the official shapes of CPSV-AP 3.2.0 and CCCEV 2.1.0 in `ontology/shapes/`, collected with `scripts/collect.py shapes`.
  - `ontology/shapes/README.md` records the SHA-256 of each stored file's bytes.
  - Statute units count as `eli:LegalResource`, because ELI makes subdivisions a kind of it, and as `cccev:ReferenceFramework`. Their versions do not.
  - The export states these types for each unit, so that the file validates without the alignment.
  - Public organisations count as `org:Organization`, because CPSV-AP makes Public Organisation a subclass of it, and the shape of a channel's `ownedBy` requires that class. The export states this type too.
  - `Participation` without `hasParticipant` is a documented deviation, because party types defined by law are not specific agents. It covers only the missing value.

## Review

Notes written by the LLM move through three statuses in order.

1. `draft`: created or edited by the LLM
   - Any edit, or any change in a cited block, returns a note to `draft`.
   - Log the reason in `log.md`.
2. `verified`: checked by a separate agent
   - The verifier did not write the note and works in a fresh context.
   - Run it as a subagent with model `opus`.
     - Use effort `xhigh` for the first verification of a note and after any change to what it states: a reading, a condition, a scope, a number, a date or an expression.
     - Use effort `high` after a change that states nothing new, such as a typo, a footnote label or a sentence moved within the note.
     - When unsure, use `xhigh`, because a wrong pass enters the ledger and later notes build on it.
   - Give it the note, the cited blocks and the notes that link to or from the note, which `uv run python -X utf8 scripts/verify.py context <note>...` prints.
   - It compares every factual sentence with the cited blocks, checks schema conformance and looks for contradictions with the linked notes.
   - On any mismatch, the note stays `draft` and the required fixes go to `log.md`.
3. `reviewed`: approved by the human owner
   - Record `reviewedBy` and `lastReviewed`.
   - The LLM never sets `reviewed`, `reviewedBy` or `lastReviewed`.
   - `.claude/settings.json` runs `scripts/review_guard.py` before every Claude Code edit and shell command. It blocks writing these into notes of `wiki/` and `synthetic/`, and any edit of a reviewed note that does not set its status to draft.
   - Its shell check reads only the command text, so a script that writes them from its own code is not stopped.

- Statute notes generated by script start as `verified`, because the script checks them against the raw source.
- Append one line to `ontology/verification.jsonl` for every generated or verified note.
  - Key it by `identifier`.
  - Record the hash of the note without `status`, `reviewedBy` and `lastReviewed`, and the hashes of the cited blocks.
  - Record the generator and its commit, or the verifier's model, effort and session.
  - For a note the verifier passed, `uv run python -X utf8 scripts/verify.py record --model opus --effort <effort> --session <id> <note>...` writes the line and sets `verified`.
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
5. Update `index.md` with `uv run python -X utf8 scripts/index.py`, and append to `log.md`.

### Query

Query answers a question from the wiki.

- Link the notes that the answer rests on.
- If the wiki lacks the answer, say so and propose sources to collect.

### Lint

Lint checks the wiki for these problems with `uv run python -X utf8 scripts/lint.py`.

- Links
  - Broken links, and links to blocks, quotations or headings that the target note does not declare
  - Notes outside the graph: no other note links to them, and they link only to statute and raw notes, except generated statute notes
  - `source` values that point to anything other than a raw note, a statute block or a quotation
- Schema
  - Notes that fail `uv run python -X utf8 scripts/vault.py check`, which validates them against LinkML, the SHACL shapes of the schema and the official shapes in `ontology/shapes/`
  - `ontology/schema.md` out of date with `ontology/schema.yaml`
  - Canvases in `views/` out of date with the notes, the schema or the competency question queries
  - Duplicate file names, identifiers or aliases
- Rules
  - `unaryTests` and FEEL expressions that do not parse
  - Tests or expressions whose types do not match the `typeRef` of their concepts
  - FEEL names that are not in `requiredInput`
  - Decision table inputs missing from `requiredInput`, and outputs other than `variable`
  - `UNIQUE` decision tables with overlapping rows, where the tests have literal bounds
- Sources
  - Factual sentences, callout titles that end like a sentence included, whose footnotes cite no statute block, quotation or raw note
  - Quotes or numbers that do not match the cited block, numbers in other units, and numbers written in Korean numerals
  - Quotes in marks other than “ ”, and lines of question callouts that are not questions
  - Footnote links to statute blocks without the citation label, or with a part that the block lacks
  - Calculation operands outside the cited blocks, or outside the sentence too when the footnote marks an example
  - Numbers and dates of frontmatter values outside the blocks of `source` and `isDerivedFrom`, or in another unit
  - Facts that cite a version not in force on the reference date, without a date condition in `appliesWhen` or in the test of the criterion itself, or outside the dates of those conditions
  - Cited blocks whose hash differs from the one in the verification ledger
  - `verified` or `reviewed` notes without a matching ledger entry, or whose entry lacks a cited block
  - `reviewed` notes without `reviewedBy` and `lastReviewed`
  - Versions of one unit with the same date, or whose dates overlap
  - Scheduled versions that come into force on or before the reference date
- Secrets
  - `.env` values in tracked files
  - Credential parameters in raw URLs
- Synthetic data
  - Links, embeds and Markdown links from `wiki/` to `synthetic/`, by path or by file name

Lint compares each number with the cited blocks, not the claim it makes. A sentence that puts two numbers of a block together wrongly passes, and so does `duration("P15D")` for "다음 달 15일까지", whose 15일 is in the block. The verifier agent compares the meaning.

### Competency questions

`docs/competency-questions.md` lists the questions the ontology must answer, with expected answers that cite the provisions they rest on.

- Check them with `uv run python -X utf8 scripts/cq.py`.
- A question is checked when `ontology/cq/<id>.rq` holds its query.
  - The query runs on the export and returns `?item` and `?source` rows: the parts of the answer and the statute units or blocks they rest on.
- Every provision the expected answer cites must be among the sources, or contain one of them.
  - Citations under 범위 밖, 관련 사항 and 검사 항목 are not part of the expected answer.
  - An item of a 별표 or 별지 서식 resolves to the whole unit, because their notes declare no item blocks, so the verifier compares the items.
- A query fails when a BIND or FILTER uses a variable that its own group does not bind.
  - SPARQL evaluates the group before the outer pattern, so the variable is unbound there and a later triple pattern matches every note, as `{ BIND(?rule AS ?item) } UNION { … }` did.
- `scripts/cq.py` also checks the scenarios in `docs/scenarios.md`.
  - A numbered step names its service by `identifier`, as in "서비스는 `job-application`(구직신청)이다", and its 선행 조건 by step number, as in "선행 조건은 3단계 구직 등록이다".
  - The service of a step must `requires` the service of each step that is its 선행 조건.
  - Every competency question a step lists must have a query and pass.

### Decisions

The human owner decides what the wiki covers where the sources leave a question open, such as leaving a case out of scope, but not how a statute is read. A reading that no source settles stays a question.

- Record each answer in `docs/decisions.md` before changing a note.
  - Give each decision a heading `## <date> <task ID>`, with the items 질문, 판단, 보류 and 반영.
  - Quote the owner's words verbatim inside “ ” in 판단, one line per point, each ending in a block ID such as `^deadline-reading-1`.
  - Never edit a recorded decision. Record a change as a new decision that names the block it replaces.
- In each note, replace an answered question with the reading.
  - Start the sentence with 이 노트는, footnote it with the blocks it reads, and add a footnote to the decision labelled `판단 기록 <task ID>`, as in `[^4]: [[decisions#^deadline-reading-1|판단 기록 deadline-reading]]`.
  - Keep decisions out of `source`. A decision settles how the cited blocks are read and is not a source of facts, so a sentence that cites only a decision has no source.
  - Keep a question that the owner leaves open, and list it under 보류.
- Return each changed note to `draft` and verify it. `scripts/verify.py context` prints the decision record, and the verifier checks that each reading says what the decision says.
- Log the operation as `review`.

### Views

Obsidian's graph view draws links without their kind, so `views/` shows the ontology in canvases, whose edges carry labels, and in bases.

- Regenerate the canvases with `uv run python -X utf8 scripts/canvas.py` after changing notes, the schema or a query in `ontology/cq/`.
  - `views/schema.canvas` shows the classes grouped by standard, with their object properties and `is_a` as labelled edges.
  - `views/역량 질문/` holds one canvas per checked competency question: the notes its query returns, the notes the query names, the notes that join them, and the statute blocks they cite in `source`.
  - Each edge is labelled with the property of the note it starts from.
- Write the bases in `views/` by hand: tables per class and a queue of notes the human owner has not reviewed.
- The graph view in `.obsidian/graph.json` colors notes by class folder, with the colors of the canvases.
- Commit changes to `.obsidian/` with the work that makes them, but keep `workspace.json` and `workspace-mobile.json` out of Git.

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
  - Check formatting with `npx markdownlint-cli2 "**/*.md"`, configured in `.markdownlint.jsonc` with ignored paths in `.markdownlint-cli2.jsonc`.
  - `wiki/.markdownlint.jsonc` turns off MD041, because vault notes have no `#` heading.
  - The statute note folders also turn off MD029, MD030 and MD052, which statute text trips with its 호 numbers and bracketed notes, and MD033 and MD045 for the image text kept in comments.

### Scripts

- Run Python with `uv run python -X utf8`.
  - Without UTF-8 mode, Python on Windows reads Korean files as CP949.
- Write files in UTF-8 with LF line endings.
- Keep every script check reproducible with the fixture notes in `tests/fixtures/`.
  - Run the tests with `uv run python -X utf8 -m pytest`.
- Enable the pre-commit hook with `git config core.hooksPath .githooks` in every clone.
  - It runs `scripts/secret_scan.py`, which rejects staged files that contain `.env` values.

### Commits

- Write the subject as `type(scope): 한국어 요약`.
  - Type and scope are lowercase English.
  - The scope is optional.
- Write the body as a short `-` list after a blank line.
- Commit each unit of work on `main`.

<!-- roadock-template: 1 -->
## ROADOCK

[Template source](https://github.com/utact/roadock/blob/main/templates/roadock-agent.md)

- Maintain `TODO.md` under `## Human` and `## Agent`; subheadings inherit the owner.
- Assign ownership by who must act, not importance.
- Human: only actions the agent cannot perform that require user intervention for current or next work.
  Examples: issuing credentials, account setup, granting access, physical-device tests, and decisions that block progress.
- Do not create Human tasks for abstract policy reviews, generic approvals, routine design choices, or speculative future decisions.
- Agent: implementation, investigation, design, technical decisions, and verification.
  Choose reasonable defaults within the user's instructions.
  Unscoped tasks are treated as Agent.
- Focus on actionable current and next steps, with immediately actionable pending tasks first.
  Avoid speculative or duplicate tasks; retain all necessary work even when the list is long.
- Write one self-contained Korean action per task, preferably within 24 characters including spaces, excluding metadata.
  Prioritize clarity over the length target.
- Give each Human task a unique, stable `<!-- roadock:task-id -->` suffix; preserve it when editing or moving the task.
- Add `Requires: task-id` below an Agent task only when an incomplete Human task blocks that action.
  Separate multiple Human IDs with commas.
  Continue independent Agent work.
- Read `TODO.md` before work; update affected tasks and next steps with related changes.
- Never mark Human tasks complete without user confirmation.
- Refresh remote changes before editing or pushing; preserve mobile Human completions when resolving conflicts.
- Add indented plain-text notes directly below a task when its scope or completion criteria need context.
  Indent notes at least two spaces beyond the checkbox line; keep them before child tasks or headings.
  Use short paragraphs and Markdown links to relevant project documents. Never include secrets.
- Roadock displays task text, Human/Agent labels, and waiting labels for `Requires`.
  Notes appear in task details in the app; headings stay hidden. Dependencies are informational, not enforced.
- Commit checklist updates with related changes; push only with explicit approval.

```markdown
## Human
- [ ] API 키 발급 <!-- roadock:api-key -->
  서비스에서 프로젝트용 키를 발급하고 앱의 인증 설정에 등록한다. 키 값은 이 파일에 적지 않는다.

## Agent
- [ ] 인증 방식 비교·설계
  기존 권한과 비용을 비교하고 기본안을 정한다. 키 발급을 기다리지 않고 진행한다.
- [ ] 발급 키로 API 호출 검증
  Requires: api-key
  실제 응답과 인증 실패 처리를 확인한다.
```
<!-- /roadock-template -->
