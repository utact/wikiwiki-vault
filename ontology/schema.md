# Ontology schema

고용24가 다루는 고용 분야의 class와 property 정의다. class와 property는 표준의 이름을 그대로 쓰고, 각 이름은 표준 IRI에 대응한다.

이 문서는 `ontology/schema.yaml`에서 `scripts/schema_doc.py`로 생성한다. 이 문서를 직접 고치지 않는다.

- 노트의 파일 이름은 RDF로 옮길 때 `skos:prefLabel`이 된다.
- instance가 아니라 노트를 설명하는 property에는 `describes: note` annotation을 붙인다. RDF로 옮길 때 이런 property는 노트 문서(`foaf:Document`)에 붙이고, 노트 문서는 `foaf:primaryTopic`으로 instance를 가리킨다.
- 표준에 없는 개념이 필요하면 이 schema에 먼저 정의하고 이유를 comments에 적는다.

## Standards

class를 정의하는 표준은 Classes 표의 순서로, property만 쓰는 표준은 접두어의 알파벳순으로 둔다.

| 접두어 | 표준 | 이름공간 |
| --- | --- | --- |
| `cpsv` | CPSV-AP 3.2.0 (Core Public Service Vocabulary Application Profile) | `http://purl.org/vocab/cpsv#` |
| `cv` | CPSV-AP 3.2.0, CCCEV 2.1.0 (Core Criterion and Core Evidence Vocabulary) | `http://data.europa.eu/m8g/` |
| `foaf` | FOAF (Friend of a Friend) | `http://xmlns.com/foaf/0.1/` |
| `eli` | ELI 1.4 (European Legislation Identifier) | `http://data.europa.eu/eli/ontology#` |
| `skos` | SKOS (Simple Knowledge Organization System) | `http://www.w3.org/2004/02/skos/core#` |
| `dcat` | DCAT (Data Catalog Vocabulary) | `http://www.w3.org/ns/dcat#` |
| `dmn` | DMN 1.3 (Decision Model and Notation) | `https://www.omg.org/spec/DMN/20191111/MODEL/` |
| `prov` | PROV-O (PROV Ontology) | `http://www.w3.org/ns/prov#` |
| `dct` | DCMI Metadata Terms | `http://purl.org/dc/terms/` |
| `employment` | 이 ontology | `https://w3id.org/kr-employment/` |
| `org` | W3C Organization Ontology | `http://www.w3.org/ns/org#` |
| `rdf` | RDF | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `rdfs` | RDF Schema | `http://www.w3.org/2000/01/rdf-schema#` |
| `schema` | Schema.org | `http://schema.org/` |
| `sh` | SHACL (Shapes Constraint Language) | `http://www.w3.org/ns/shacl#` |
| `spdx` | SPDX | `http://spdx.org/rdf/terms#` |

## Classes

`wiki/` 노트의 `type`에 쓰는 class다. CPSV-AP, CCCEV, ELI, SKOS, DCAT 순서로 묶는다.

| 이름 | 표준 | 뜻 | 예 |
| --- | --- | --- | --- |
| `PublicService` | `cpsv:PublicService` | 공공기관이 제공하는 서비스(급여와 신청 절차 포함) | 구직급여, 실업인정, 피보험자격 상실 신고 |
| `LifeEvent` | `cv:LifeEvent` | 공공서비스가 필요해지는 개인의 사건 | 이직, 재취업 |
| `BusinessEvent` | `cv:BusinessEvent` | 공공서비스가 필요해지는 사업장의 사건 | 근로자 이직 |
| `Agent` | `foaf:Agent` | 서비스에 참여하는 당사자 | 사업주, 피보험자, 수급자격자 |
| `PublicOrganisation` | `cv:PublicOrganisation` | 공공기관 | 고용노동부, 직업안정기관, 근로복지공단 |
| `Participation` | `cv:Participation` | 서비스에서 당사자가 맡는 역할 | 피보험자격 상실 신고의 신고 의무자인 사업주 |
| `Channel` | `cv:Channel` | 서비스를 이용하는 경로 | 고용24 누리집, 직업안정기관 출석 |
| `Output` | `cv:Output` | 서비스가 만들어 내는 결과 | 수급자격 인정, 수급자격증 |
| `Rule` | `cpsv:Rule` | 서비스가 따르는 산정·판단 규칙 | 구직급여일액 산정, 소정급여일수 산정 |
| `Criterion` | `cv:Criterion` | 서비스를 받으려면 충족해야 하는 조건 | 기준기간 동안의 피보험 단위기간 180일 이상 |
| `Constraint` | `cv:Constraint` | 정보 값에 거는 기한·상한·하한 같은 제한 | 기초일액 상한 11만3500원, 이직확인서 발급 기한 10일 |
| `InformationConcept` | `cv:InformationConcept` | 조건과 규칙이 판단하는 정보 항목 | 피보험 단위기간, 이직일, 기초일액 |
| `EvidenceType` | `cv:EvidenceType` | 증빙 서류의 유형 | 피보험자 이직확인서 |
| `LegalResource` | `eli:LegalResource` | 시행일 버전과 무관한 법령 | 고용보험법, 2026년 적용 최저임금 고시 |
| `LegalResourceSubdivision` | `eli:LegalResourceSubdivision` | 시행일 버전과 무관한 법령의 하위 단위 | 고용보험법 제40조, 고용보험법 별표 1, 고용보험법 시행규칙 별지 제6호서식 |
| `ConceptScheme` | `skos:ConceptScheme` | 용어집과 코드 체계 | 고용보험 상실사유 구분코드, 당사자 역할 |
| `Concept` | `skos:Concept` | 용어, 코드 값, 역할, 대상자 유형 | 상실사유 구분코드 23, 신고 의무자 |
| `Dataset` | `dcat:Dataset` | 통계와 데이터셋 | 구직급여 수급 현황 |

- `Agent`: 법령이 정한 당사자 유형도 instance로 둔다.
- `Rule`: 식은 FEEL literal expression으로, 표는 DMN 결정표로 적는다.
- `Rule`: `literalExpression`과 `decisionTable` 중 하나만 적는다.
- `LegalResource`: 법률, 시행령, 시행규칙, 고시를 포함한다.
- `LegalResource`: identifier는 법령이면 law-<법령ID>, 행정규칙이면 admrul-<행정규칙ID>다.
- `LegalResourceSubdivision`: 장, 절, 조, 별표, 별지 서식, 부칙을 포함한다.
- `LegalResourceSubdivision`: identifier는 소속 법령의 identifier 뒤에 단위를 붙인다. 조는 -art-<번호>, 가지번호는 -art-10-2처럼 붙인다.
- `LegalResourceSubdivision`: 장은 -ch-<번호>, 절은 -ch-<번호>-sec-<번호>, 별표는 -annex-<번호>, 별지 서식은 -form-<번호>, 부칙은 -sup-<공포번호>다.

아래 추상 class는 `type`에 쓰지 않고, 공통 property를 묶는 데만 쓴다.

- `Event`(`cv:Event`): 공공서비스가 필요해지는 사건
- `Requirement`(`cv:Requirement`): Criterion과 Constraint의 상위 class
- `Work`(`eli:Work`): 법령과 그 하위 단위의 공통 상위 class

## Common properties

모든 `wiki/` 노트에 쓰는 property다. 내용, 근거, 적용 기간, 편집 상태의 순서로 둔다. frontmatter에도 이 순서로 적고, class별 property는 `definition`과 `source` 사이에 둔다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `type` | `rdf:type` | 예 | Classes 표의 이름 |
| `identifier` | `dct:identifier` | 예 | 바뀌지 않는 kebab-case 식별자 |
| `aliases` | `skos:altLabel` | 아니요 | 다른 이름 목록 |
| `definition` | `skos:definition` | 예 | 한 문장 정의 |
| `source` | `dct:source` | 예 | 원문 노트나 법령 노트의 wikilink 목록 |
| `validFrom` | `schema:validFrom` | 아니요 | 적용 시작일 (date) |
| `validThrough` | `schema:validThrough` | 아니요 | 적용 종료일 (date) |
| `status` | `schema:creativeWorkStatus` | 예 | 노트의 편집 상태: `draft`(LLM이 만들거나 고친 상태), `verified`(노트를 쓰지 않은 별도 agent가 원문과 대조한 상태), `reviewed`(사람이 승인한 상태) |
| `reviewedBy` | `schema:reviewedBy` | 아니요 | 승인한 사람 |
| `lastReviewed` | `schema:lastReviewed` | 아니요 | 승인일 (date) |
| `isReplacedBy` | `dct:isReplacedBy` | 아니요 | 폐지되거나 대체된 instance를 잇는 후속 instance (`NamedThing`) |

`source`, `status`, `reviewedBy`, `lastReviewed`는 instance가 아니라 노트를 설명한다.

## Object properties

다른 노트를 wikilink로 가리키는 class별 property다. 관계마다 이 표의 방향으로만 적는다. 표 안에서는 필수 property를 먼저, 나머지를 알파벳순으로 둔다.

### PublicService

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `hasCompetentAuthority` | `cv:hasCompetentAuthority` | 예 | 서비스를 책임지는 공공기관 (`PublicOrganisation`) |
| `audience` | `dct:audience` | 아니요 | 서비스의 대상자 유형 (`Concept`) |
| `follows` | `cpsv:follows` | 아니요 | 서비스가 따르는 규칙 (`Rule`) |
| `hasChannel` | `cv:hasChannel` | 아니요 | 서비스를 이용하는 경로 (`Channel`) |
| `hasInputType` | `cv:hasInputType` | 아니요 | 서비스에 필요한 증빙 유형 (`EvidenceType`) |
| `hasLegalResource` | `cv:hasLegalResource` | 아니요 | 서비스의 근거 법령이나 그 하위 단위 (`Work`) |
| `hasParticipation` | `cv:hasParticipation` | 아니요 | 서비스에서 당사자가 맡는 역할 (`Participation`) |
| `holdsRequirement` | `cv:holdsRequirement` | 아니요 | 서비스의 조건이나 제한 (`Requirement`) |
| `isGroupedBy` | `cv:isGroupedBy` | 아니요 | 서비스를 필요로 하는 사건 (`Event`) |
| `produces` | `cpsv:produces` | 아니요 | 서비스의 결과 (`Output`) |
| `relatedService` | `cv:relatedService` | 아니요 | 관련 서비스 (`PublicService`) |
| `requires` | `dct:requires` | 아니요 | 먼저 거쳐야 하는 서비스 (`PublicService`) |

### Event

`LifeEvent`, `BusinessEvent`에 쓴다.

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `eventType` | `dct:type` | 아니요 | 사건의 유형 코드 (`Concept`) |

### PublicOrganisation

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `subOrganizationOf` | `org:subOrganizationOf` | 아니요 | 상위 공공기관 (`PublicOrganisation`) |

### Participation

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `hasParticipant` | `cv:hasParticipant` | 예 | 역할을 맡는 당사자 (`Agent`) |
| `role` | `cv:role` | 예 | 당사자가 맡는 역할 (`Concept`) |

### Channel

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `ownedBy` | `cv:ownedBy` | 아니요 | 경로를 운영하는 공공기관 (`PublicOrganisation`) |

### Rule

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `implements` | `cpsv:implements` | 예 | 규칙의 근거 법령이나 그 하위 단위 (`Work`) |
| `variable` | `dmn:variable` | 예 | 규칙이 산출하는 정보 항목 (`InformationConcept`) |
| `requiredInput` | `dmn:requiredInput` | 아니요 | 규칙의 입력 정보 항목 (`InformationConcept`) |

- `requiredInput`: FEEL 식에서는 노트 이름을 변수 이름으로 쓴다.

### Requirement

`Criterion`, `Constraint`에 쓴다.

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `hasConcept` | `cv:hasConcept` | 아니요 | 판단하는 정보 항목 (`InformationConcept`) |
| `hasEvidenceTypeList` | `cv:hasEvidenceTypeList` | 아니요 | 조건을 증명하는 증빙 유형 (`EvidenceType`) |
| `hasRequirement` | `cv:hasRequirement` | 아니요 | 하위 조건이나 제한 (`Requirement`) |
| `isDerivedFrom` | `cv:isDerivedFrom` | 아니요 | 조건이나 제한의 근거 법령 단위 (`Work`) |

- `hasEvidenceTypeList`: 적은 증빙 유형이 모두 필요하다. 서로 대신할 수 있는 조합이 있으면 조합마다 조건을 나눈다.
- `hasEvidenceTypeList`: CCCEV의 증빙 유형 목록(`cv:EvidenceTypeList`)은 RDF로 옮길 때 만든다.
- `hasRequirement`: 하위 조건이나 제한을 모두 충족할 때 상위 조건이나 제한이 적용된다.

### Constraint

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `constrains` | `cv:constrains` | 예 | 제한하는 정보 항목 (`InformationConcept`) |

### EvidenceType

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `isDefinedBy` | `rdfs:isDefinedBy` | 아니요 | 증빙 유형을 정한 별지 서식 (`LegalResourceSubdivision`) |

### Work

`LegalResource`, `LegalResourceSubdivision`에 쓴다.

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `basedOn` | `eli:based_on` | 아니요 | 위임한 상위 법령이나 그 하위 단위 (`Work`) |
| `cites` | `eli:cites` | 아니요 | 본문이 인용하는 법령이나 그 하위 단위 (`Work`) |

### LegalResource

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `typeDocument` | `eli:type_document` | 예 | 법률, 대통령령, 부령, 고시 같은 법령 종류 (`Concept`) |

### LegalResourceSubdivision

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `isPartOf` | `eli:is_part_of` | 예 | 속한 법령이나 상위 단위 (`Work`) |

### Concept

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `inScheme` | `skos:inScheme` | 예 | 속한 용어집이나 코드 체계 (`ConceptScheme`) |
| `broader` | `skos:broader` | 아니요 | 상위 개념 (`Concept`) |
| `related` | `skos:related` | 아니요 | 관련 개념 (`Concept`) |

### Dataset

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `publisher` | `dct:publisher` | 예 | 공개 기관 (`PublicOrganisation`) |

## Datatype properties

wikilink가 아닌 값을 담는 class별 property다. 배치 기준은 Object properties와 같다.

### Rule

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `decisionTable` | `dmn:decisionTable` | 아니요 | 규칙의 결정표 (`DecisionTable`) |
| `literalExpression` | `dmn:literalExpression` | 아니요 | 규칙의 FEEL 식 |

### Constraint

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `currency` | `schema:currency` | 아니요 | ISO 4217 통화 코드 |
| `maxExclusive` | `sh:maxExclusive` | 아니요 | 미만 (decimal) |
| `maxInclusive` | `sh:maxInclusive` | 아니요 | 이하 (decimal) |
| `minExclusive` | `sh:minExclusive` | 아니요 | 초과 (decimal) |
| `minInclusive` | `sh:minInclusive` | 아니요 | 이상 (decimal) |
| `unitCode` | `schema:unitCode` | 아니요 | UN/CEFACT 단위 코드 |
| `value` | `schema:value` | 아니요 | 고정 값 (decimal) |

- `unitCode`: 일은 DAY, 월은 MON, 년은 ANN, 시간은 HUR다.

### Work

`LegalResource`, `LegalResourceSubdivision`에 쓴다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `title` | `dct:title` | 예 | 제목 |
| `idLocal` | `eli:id_local` | 아니요 | 법제처 식별자 |

- `idLocal`: 법령은 법령ID, 행정규칙은 행정규칙ID다.

### LegalResourceSubdivision

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `number` | `eli:number` | 예 | 제40조, 별표 1 같은 하위 단위 번호 |
| `typeSubdivision` | `eli:type_subdivision` | 예 | 하위 단위의 종류: `chapter`(장), `section`(절), `article`(조), `annex`(별표), `form`(별지 서식), `addendum`(부칙) |

### Concept

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `exactMatch` | `skos:exactMatch` | 아니요 | 다른 체계의 같은 개념 |
| `notation` | `skos:notation` | 아니요 | 코드 값 |

## Decision tables

Rule의 `decisionTable` 안에 inline으로 적는 DMN 결정표 구조다. 배치 기준은 Object properties와 같다.

### DecisionTable

`DecisionTable`(`dmn:decisionTable`): Rule의 결정표

- 행마다 입력 조건과 출력 값을 적는다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `hitPolicy` | `dmn:hitPolicy` | 예 | 여러 행이 맞을 때의 처리 방식: `unique`(맞는 규칙이 하나뿐이어야 함), `first`(맞는 규칙 중 첫 번째 규칙의 결과), `any`(맞는 규칙들의 결과가 모두 같아야 함) |
| `input` | `dmn:input` | 예 | 입력 열 목록 (`InputClause`) |
| `output` | `dmn:output` | 예 | 출력 열 목록 (`OutputClause`) |
| `rule` | `dmn:rule` | 예 | 행 목록 (`DecisionRule`) |

### InputClause

`InputClause`(`dmn:input`): 결정표의 입력 열

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `hasConcept` | `cv:hasConcept` | 예 | 입력 열의 정보 항목 (`InformationConcept`) |

### OutputClause

`OutputClause`(`dmn:output`): 결정표의 출력 열

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `hasConcept` | `cv:hasConcept` | 예 | 출력 열의 정보 항목 (`InformationConcept`) |
| `currency` | `schema:currency` | 아니요 | ISO 4217 통화 코드 |
| `unitCode` | `schema:unitCode` | 아니요 | UN/CEFACT 단위 코드 |

- `unitCode`: 일은 DAY, 월은 MON, 년은 ANN, 시간은 HUR다.

### DecisionRule

`DecisionRule`(`dmn:rule`): 결정표의 한 행

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `inputEntry` | `dmn:inputEntry` | 예 | 입력 열 순서대로 적은 FEEL unary test |
| `outputEntry` | `dmn:outputEntry` | 예 | 출력 열 순서대로 적은 FEEL 식 |

- `inputEntry`: 50세 미만은 `< 50`, 1년 이상 3년 미만은 `[1..3)`처럼 적는다.

## Raw source properties

`raw/` 노트의 frontmatter에 이 표의 순서로 적는 property다. 원문은 wiki보다 먼저 존재하므로 wikilink를 쓰지 않는다.

`Entity`(`prov:Entity`): `raw/` 노트의 원문

- 법령 원문 노트 하나는 시행일 버전 하나에 해당한다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `title` | `dct:title` | 예 | 제목 |
| `publisher` | `dct:publisher` | 예 | 공개 기관 |
| `url` | `schema:url` | 예 | 수집한 주소 (uri) |
| `generatedAtTime` | `prov:generatedAtTime` | 예 | 수집 일시 (datetime) |
| `sha256` | `spdx:checksumValue` | 예 | 정규화한 본문 텍스트의 SHA-256 hash |
| `license` | `dct:license` | 예 | 이용 조건 |
| `modified` | `dct:modified` | 아니요 | 원문이 밝힌 최종 수정일 (date) |
| `idLocal` | `eli:id_local` | 아니요 | 법제처 식별자 |
| `number` | `eli:number` | 아니요 | 법령 원문 버전의 법령일련번호(MST) |
| `firstDateEntryInForce` | `eli:first_date_entry_in_force` | 아니요 | 법령 원문 버전의 시행일자 (date) |
| `datePublication` | `eli:date_publication` | 아니요 | 법령 원문 버전의 공포일자 (date) |

- `url`: 인증값은 `${LAW_OC}`처럼 환경변수 이름으로 치환한다.
- `idLocal`: 법령은 법령ID, 행정규칙은 행정규칙ID다.

## Synthetic data

`synthetic/` 노트에만 쓰는 class와 property다. frontmatter에 이 표의 순서로 적는다.

### Person

`Person`(`foaf:Person`): 합성데이터의 개인

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `type` | `rdf:type` | 예 | Classes 표의 이름 |
| `identifier` | `dct:identifier` | 예 | 바뀌지 않는 kebab-case 식별자 |
| `synthetic` | `employment:synthetic` | 예 | 합성데이터 표시 (boolean) |

- `synthetic`: 값은 항상 true다.

### Evidence

`Evidence`(`cv:Evidence`): 합성데이터의 증빙 서류

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `type` | `rdf:type` | 예 | Classes 표의 이름 |
| `identifier` | `dct:identifier` | 예 | 바뀌지 않는 kebab-case 식별자 |
| `synthetic` | `employment:synthetic` | 예 | 합성데이터 표시 (boolean) |
| `conformsTo` | `dct:conformsTo` | 예 | 합성 증빙이 따르는 증빙 유형 (`EvidenceType`) |

- `synthetic`: 값은 항상 true다.
