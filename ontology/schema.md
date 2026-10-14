# Ontology schema

class와 property는 공공서비스·법령·용어 표준의 이름을 그대로 쓰고, 각 이름은 표준 IRI에 대응한다. 표준에 없는 개념이 필요하면 이 문서에 먼저 정의하고 이유를 적는다.

## Standards

class를 정의하는 표준은 Classes 표의 순서로, property만 쓰는 표준은 접두어의 알파벳순으로 둔다.

| 접두어 | 표준 | 이름공간 |
| --- | --- | --- |
| `cpsv` | CPSV-AP 3.2.0 (Core Public Service Vocabulary Application Profile) | `http://purl.org/vocab/cpsv#` |
| `cv` | CPSV-AP 3.2.0, CCCEV 2.1.0 (Core Criterion and Core Evidence Vocabulary) | `http://data.europa.eu/m8g/` |
| `eli` | ELI (European Legislation Identifier) | `http://data.europa.eu/eli/ontology#` |
| `skos` | SKOS (Simple Knowledge Organization System) | `http://www.w3.org/2004/02/skos/core#` |
| `dcat` | DCAT (Data Catalog Vocabulary) | `http://www.w3.org/ns/dcat#` |
| `foaf` | FOAF (Friend of a Friend) | `http://xmlns.com/foaf/0.1/` |
| `adms` | ADMS (Asset Description Metadata Schema) | `http://www.w3.org/ns/adms#` |
| `dct` | DCMI Metadata Terms | `http://purl.org/dc/terms/` |
| `org` | W3C Organization Ontology | `http://www.w3.org/ns/org#` |
| `prov` | PROV-O (PROV Ontology) | `http://www.w3.org/ns/prov#` |
| `rdf` | RDF | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `schema` | Schema.org | `https://schema.org/` |
| `spdx` | SPDX | `http://spdx.org/rdf/terms#` |

## Classes

class는 정의한 표준별로 묶어 Standards 표의 순서로 둔다.

| 이름 | 표준 | 뜻 | 예 |
| --- | --- | --- | --- |
| `PublicService` | `cpsv:PublicService` | 공공기관이 제공하는 서비스(급여와 신청 절차 포함) | 구직급여, 실업인정, 구직신청 |
| `LifeEvent` | `cv:LifeEvent` | 공공서비스가 필요해지는 개인의 사건 | 이직, 재취업 |
| `BusinessEvent` | `cv:BusinessEvent` | 공공서비스가 필요해지는 사업장의 사건 | 근로자 이직 |
| `PublicOrganisation` | `cv:PublicOrganisation` | 공공기관 | 고용노동부, 고용센터, 근로복지공단 |
| `Channel` | `cv:Channel` | 서비스를 이용하는 경로 | 고용24 누리집, 고용센터 방문 |
| `Output` | `cv:Output` | 서비스가 만들어 내는 결과 | 수급자격 인정 |
| `Rule` | `cpsv:Rule` | 서비스가 따르는 산정·판단 규칙 | 소정급여일수 산정 |
| `Criterion` | `cv:Criterion` | 서비스를 받으려면 충족해야 하는 조건 | 피보험단위기간 180일 이상 |
| `Constraint` | `cv:Constraint` | 정보 값에 거는 기한·상한·하한 같은 제한 | 수급기간 12개월 |
| `InformationConcept` | `cv:InformationConcept` | 조건이 판단하는 정보 항목 | 피보험단위기간, 이직일, 이직사유 |
| `EvidenceType` | `cv:EvidenceType` | 증빙 서류의 유형 | 이직확인서 |
| `LegalResource` | `eli:LegalResource` | 법률, 시행령, 시행규칙, 고시 | 고용보험법 |
| `LegalResourceSubdivision` | `eli:LegalResourceSubdivision` | 조문과 별표 | 고용보험법 제40조 |
| `ConceptScheme` | `skos:ConceptScheme` | 용어집과 코드 체계 | 고용보험 상실사유 코드 |
| `Concept` | `skos:Concept` | 용어, 코드 값, 대상자 유형 | 피보험자, 상실사유 코드 값 |
| `Dataset` | `dcat:Dataset` | 통계와 데이터셋 | 구직급여 수급 현황 |

합성데이터에만 쓰는 class는 `Person`(`foaf:Person`)과 `Evidence`(`cv:Evidence`)다. 실제 개인과 실제 서류는 wiki에 두지 않는다.

## Common properties

모든 `wiki/` 노트에 쓰는 property다. 내용, 근거, 적용 기간, 관리 상태의 순서로 둔다. frontmatter에도 이 순서로 적고, object property는 `definition`과 `source` 사이에 둔다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `type` | `rdf:type` | 예 | Classes 표의 이름 |
| `identifier` | `dct:identifier` | 예 | kebab-case 식별자 |
| `aliases` | `skos:altLabel` | | 다른 이름 목록 |
| `definition` | `skos:definition` | 예 | 한 문장 정의 |
| `source` | `dct:source` | 예 | 원문 노트나 조문 노트의 wikilink 목록 |
| `validFrom` | `schema:validFrom` | | 적용 시작일 `YYYY-MM-DD` |
| `validThrough` | `schema:validThrough` | | 적용 종료일 `YYYY-MM-DD` |
| `status` | `adms:status` | 예 | `draft`, `verified`, `reviewed`, `deprecated` |
| `reviewedBy` | `schema:reviewedBy` | | 승인한 사람 |
| `lastReviewed` | `schema:lastReviewed` | | 승인일 `YYYY-MM-DD` |
| `isReplacedBy` | `dct:isReplacedBy` | | 대체 노트의 wikilink |

법령의 `identifier`는 법제처 식별자로 만든다. `LegalResource`는 `law-<법령ID>`, `LegalResourceSubdivision`은 `law-<법령ID>-<조문번호 6자리>`다. 제40조는 `law-<법령ID>-004000`이 된다.

## Object properties

다른 노트를 wikilink로 가리키는 property다. 관계마다 이 표의 방향으로만 적는다. class마다 표를 하나 두고 Classes 표의 순서를 따른다. 표 안에서는 필수 property를 먼저, 나머지를 알파벳순으로 둔다.

### PublicService

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `hasCompetentAuthority` | `cv:hasCompetentAuthority` | 예 | `PublicOrganisation` |
| `audience` | `dct:audience` | | 대상자 유형 `Concept` |
| `follows` | `cpsv:follows` | | `Rule` |
| `hasChannel` | `cv:hasChannel` | | `Channel` |
| `hasInputType` | `cv:hasInputType` | | `EvidenceType` |
| `hasLegalResource` | `cv:hasLegalResource` | | `LegalResource`, `LegalResourceSubdivision` |
| `holdsRequirement` | `cv:holdsRequirement` | | `Criterion`, `Constraint` |
| `isGroupedBy` | `cv:isGroupedBy` | | `LifeEvent`, `BusinessEvent` |
| `produces` | `cpsv:produces` | | `Output` |
| `relatedService` | `cv:relatedService` | | 관련 `PublicService` |
| `requires` | `dct:requires` | | 먼저 거쳐야 하는 `PublicService` |

### PublicOrganisation

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `subOrganizationOf` | `org:subOrganizationOf` | | 상위 `PublicOrganisation` |

### Channel

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `ownedBy` | `cv:ownedBy` | | 운영하는 `PublicOrganisation` |

### Rule

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `implements` | `cpsv:implements` | 예 | `LegalResource`, `LegalResourceSubdivision` |

### Criterion, Constraint

두 class는 CCCEV에서 상위 class `cv:Requirement`를 함께 쓰므로 한 표로 묶는다. `constrains`는 `Constraint`에만 쓴다.

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `isDerivedFrom` | `cv:isDerivedFrom` | 예 | 근거 `LegalResourceSubdivision` |
| `constrains` | `cv:constrains` | | 제한하는 `InformationConcept` |
| `hasConcept` | `cv:hasConcept` | | 판단하는 `InformationConcept` |
| `hasEvidenceTypeList` | `cv:hasEvidenceTypeList` | | `EvidenceType` |
| `hasRequirement` | `cv:hasRequirement` | | 하위 `Criterion`, `Constraint` |

CCCEV에서 `hasEvidenceTypeList`는 증빙 유형 목록(`cv:EvidenceTypeList`)을 가리킨다. 이 wiki에서는 목록을 따로 노트로 만들지 않고 증빙 유형을 바로 적는다. 적은 증빙은 모두 필요하다는 뜻이다. 서로 대신할 수 있는 증빙 조합이 있으면 조합마다 `Criterion`을 나눈다.

### LegalResource

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `typeDocument` | `eli:type_document` | 예 | 법률·대통령령·부령·고시 같은 법령 종류 `Concept` |
| `basedOn` | `eli:based_on` | | 위임한 상위 `LegalResource` |
| `cites` | `eli:cites` | | 인용하는 `LegalResource`, `LegalResourceSubdivision` |

### LegalResourceSubdivision

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `isPartOf` | `eli:is_part_of` | 예 | 조문이 속한 `LegalResource` |
| `cites` | `eli:cites` | | 인용하는 `LegalResource`, `LegalResourceSubdivision` |

조문 노트는 현행 법령을 기준으로 쓴다. `validFrom`에는 그 법령의 시행일자를 적는다. 항·호·목은 노트를 나누지 않고 본문의 `##` 제목으로 둔다.

### Concept

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `inScheme` | `skos:inScheme` | 예 | `ConceptScheme` |
| `broader` | `skos:broader` | | 상위 `Concept` |
| `exactMatch` | `skos:exactMatch` | | 다른 체계의 같은 `Concept` |
| `related` | `skos:related` | | 관련 `Concept` |

### Dataset

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `publisher` | `dct:publisher` | 예 | 공개한 `PublicOrganisation` |

## Datatype properties

wikilink가 아닌 값을 담는 class별 property다. 배치 기준은 Object properties와 같다.

### Concept

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `notation` | `skos:notation` | | 코드 값 |

## Raw source properties

`raw/` 노트에 쓰는 property다. 식별, 위치, 수집 시점, 무결성, 이용 조건의 순서로 두고, frontmatter에도 이 순서로 적는다. 원문은 wiki보다 먼저 존재하므로 wikilink를 쓰지 않는다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `title` | `dct:title` | 예 | 원문 제목 |
| `publisher` | `dct:publisher` | 예 | 공개 기관 이름 |
| `url` | `schema:url` | 예 | 수집한 주소 |
| `generatedAtTime` | `prov:generatedAtTime` | 예 | 수집 일시 ISO 8601 |
| `sha256` | `spdx:checksumValue` | 예 | 추출한 본문 텍스트의 SHA-256 hash |
| `license` | `dct:license` | 예 | 이용 조건 |
