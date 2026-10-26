# Ontology schema

고용24가 다루는 고용 분야의 RDF 모델이다. class와 property는 표준의 이름을 그대로 쓰고, 각 이름은 표준 IRI에 대응한다.

이 문서는 `ontology/schema.yaml`에서 `scripts/schema_doc.py`로 생성한다. 이 문서를 직접 고치지 않는다.

- 노트의 frontmatter는 작성용 형식이다. `scripts/vault.py`가 frontmatter를 이 모델의 instance와 노트 문서로 옮긴다.
- 표준에 없는 개념은 `employment:` 이름공간에 정의하고, 이유를 해당 class나 property의 comments에 적는다.

## Standards

class를 정의하는 표준은 class가 처음 나오는 순서로, property만 쓰는 표준은 접두어의 알파벳순으로 둔다.

| 접두어 | 표준 | 이름공간 |
| --- | --- | --- |
| `employment` | 이 ontology | `https://w3id.org/kr-employment/` |
| `foaf` | FOAF (Friend of a Friend) | `http://xmlns.com/foaf/0.1/` |
| `cpsv` | CPSV-AP 3.2.0 (Core Public Service Vocabulary Application Profile) | `http://purl.org/vocab/cpsv#` |
| `cv` | CPSV-AP 3.2.0, CCCEV 2.1.0 (Core Criterion and Core Evidence Vocabulary) | `http://data.europa.eu/m8g/` |
| `eli` | ELI 1.4 (European Legislation Identifier) | `http://data.europa.eu/eli/ontology#` |
| `skos` | SKOS (Simple Knowledge Organization System) | `http://www.w3.org/2004/02/skos/core#` |
| `prov` | PROV-O (PROV Ontology) | `http://www.w3.org/ns/prov#` |
| `sdo` | Schema.org | `https://schema.org/` |
| `dct` | DCMI Metadata Terms | `http://purl.org/dc/terms/` |
| `org` | W3C Organization Ontology | `http://www.w3.org/ns/org#` |
| `rdf` | RDF | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `rdfs` | RDF Schema | `http://www.w3.org/2000/01/rdf-schema#` |
| `spdx` | SPDX | `http://spdx.org/rdf/terms#` |

## Classes

`wiki/` 노트가 설명하는 instance의 class다. CPSV-AP, CCCEV, ELI, SKOS 순서로 묶는다.

| 이름 | 표준 | 뜻 | 예 |
| --- | --- | --- | --- |
| `PublicService` | `cpsv:PublicService` | 공공기관이 제공하는 서비스(급여와 신청 절차 포함) | 실업급여, 구직급여, 실업의 신고, 피보험자격 상실 신고 |
| `LifeEvent` | `cv:LifeEvent` | 공공서비스가 필요해지는 개인의 사건 | 이직, 재취업 |
| `BusinessEvent` | `cv:BusinessEvent` | 공공서비스가 필요해지는 사업장의 사건 | 근로자의 이직 |
| `PublicOrganisation` | `cv:PublicOrganisation` | 공공기관 | 고용노동부, 근로복지공단 |
| `Participation` | `cv:Participation` | 서비스에서 당사자가 맡는 역할과 그 역할의 의무 | 피보험자격 상실 신고에서 사업주가 맡는 신고 의무 |
| `Channel` | `cv:Channel` | 서비스를 이용하는 경로 | 고용24 누리집, 직업안정기관 출석 |
| `Output` | `cv:Output` | 서비스가 만들어 내는 결과 | 수급자격 인정, 수급자격증 |
| `Rule` | `cpsv:Rule` | 서비스가 따르는 산정·판단 규칙 | 구직급여일액 산정, 소정급여일수 산정 |
| `Criterion` | `cv:Criterion` | 서비스를 받으려면 충족해야 하는 조건 | 기준기간 동안의 피보험 단위기간 180일 이상, 2026-01-01 이후 이직 |
| `Constraint` | `cv:Constraint` | 정보 값에 거는 기한·상한·하한 같은 제한 | 기초일액 상한 11만3500원, 이직확인서 발급 기한 10일 |
| `InformationConcept` | `cv:InformationConcept` | 조건과 규칙이 판단하는 정보 항목 | 피보험 단위기간, 이직일, 기초일액, 이직사유 |
| `EvidenceType` | `cv:EvidenceType` | 증빙 서류의 유형 | 피보험자 이직확인서 |
| `LegalResource` | `eli:LegalResource` | 시행일 버전과 무관한 법령 | 고용보험법, 2026년 적용 최저임금 고시 |
| `LegalResourceSubdivision` | `eli:LegalResourceSubdivision` | 시행일 버전과 무관한 법령의 하위 단위 | 고용보험법 제40조, 고용보험법 별표 1, 고용보험법 시행규칙 별지 제6호서식 |
| `ConceptScheme` | `skos:ConceptScheme` | 용어집과 코드 체계 | 피보험자격 상실사유 구분코드, 고용보험 당사자 유형, 정당한 이직 사유 |
| `Concept` | `skos:Concept` | 용어, 코드 값, 당사자 유형, 사유 목록의 항목 | 상실사유 구분코드 23, 사업주 |

- `Participation`: 사업주, 피보험자 같은 당사자 유형은 `role`의 Concept로 적고 `hasParticipant`는 비워 둔다. CPSV-AP는 `hasParticipant`를 필수로 두지만, 법령이 정한 당사자 유형은 특정 Agent가 아니다.
- `Participation`: 역할에 딸린 기한 같은 의무는 `holdsRequirement`로 적는다. CPSV-AP는 이 property를 PublicService에만 두므로 Participation에 쓰는 것은 확장이다.
- `Rule`: 식은 FEEL literal expression으로, 표는 결정표로 적는다. 둘 중 하나만 적는다.
- `Rule`: 경과조치처럼 규칙이 일부 경우에만 적용되면 그 조건을 `appliesWhen`으로 잇는다.
- `Rule`: 단서나 예외처럼 규칙이 다루지 않는 경우는 그 경우가 아님을 판단하는 Criterion을 `appliesWhen`으로 이어 뺀다.
- `Constraint`: 기한은 지켜야 하는 행위의 날짜를 `constrains`로 두고, 법령 문구대로 정의한 기한일 정보 항목과 `<=`로 비교한다.
- `Constraint`: 기간의 첫날 산입처럼 법령 노트만으로 정할 수 없는 기한일 계산은 기한일 노트에 질문으로 남긴다.
- `LegalResource`: 법률, 시행령, 시행규칙, 고시를 포함한다.
- `LegalResource`: identifier는 법령이면 law-<법령ID>, 행정규칙이면 admrul-<행정규칙ID>다.
- `LegalResourceSubdivision`: 장, 절, 조, 별표, 별지 서식, 부칙은 노트로 두고, 항, 호, 목은 노트의 block으로 둔다.
- `LegalResourceSubdivision`: identifier는 소속 법령의 identifier 뒤에 단위를 붙인다. 조는 -art-40, 가지번호는 -art-10-2, 장은 -ch-4, 장의2는 -ch-5-2, 절은 -ch-4-sec-2다.
- `LegalResourceSubdivision`: 별표는 -annex-1, 별표 1의2는 -annex-1-2, 별지 서식은 -form-6, 부칙은 -sup-<공포일자>-<공포번호>다. 공포번호가 같은 부칙이 있어 공포일자를 붙인다.
- `LegalResourceSubdivision`: 버전과 무관한 block은 소속 노트의 identifier 뒤에 날짜를 뺀 block ID를 붙인다. 고용보험법 제45조제5항은 law-001761-art-45-p5다.

아래 추상 class는 instance의 class로 쓰지 않고, 공통 property를 묶는 데만 쓴다.

- `Event`(`cv:Event`): 공공서비스가 필요해지는 사건
- `Agent`(`foaf:Agent`): 서비스에 참여하는 당사자
- `Requirement`(`cv:Requirement`): Criterion과 Constraint의 상위 class
- `Work`(`eli:Work`): 법령과 그 하위 단위의 공통 상위 class

## Common properties

모든 instance의 공통 property다. 내용, 적용 기간, 대체 관계의 순서로 둔다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `type` | `rdf:type` | 예 | Classes 표의 이름 |
| `identifier` | `dct:identifier` | 예 | 바뀌지 않는 kebab-case 식별자 |
| `prefLabel` | `skos:prefLabel` | 예 | 노트의 파일 이름 |
| `aliases` | `skos:altLabel` | 아니요 | 다른 이름 목록 |
| `definition` | `skos:definition` | 예 | 한 문장 정의 |
| `validFrom` | `sdo:validFrom` | 아니요 | 달력상 적용 시작일 (date) |
| `validThrough` | `sdo:validThrough` | 아니요 | 달력상 적용 종료일 (date) |
| `isReplacedBy` | `dct:isReplacedBy` | 아니요 | 폐지되거나 대체된 instance를 잇는 후속 instance (`NamedThing`) |

- `identifier`: instance의 IRI는 base IRI 뒤에 identifier를 붙여 만든다.
- `validThrough`: 이직일 같은 사실의 날짜에 따라 달라지는 경과조치는 이 property가 아니라 Criterion으로 적는다.

## Object properties

다른 instance를 가리키는 class별 property다. 관계마다 이 표의 방향으로만 적는다. 표 안에서는 필수 property를 먼저, 나머지를 알파벳순으로 둔다.

### PublicService

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `hasCompetentAuthority` | `cv:hasCompetentAuthority` | 예 | 서비스를 책임지는 공공기관 (`PublicOrganisation`) |
| `audience` | `dct:audience` | 아니요 | 서비스의 대상자 유형 (`Concept`) |
| `follows` | `cpsv:follows` | 아니요 | 서비스가 따르는 규칙 (`Rule`) |
| `hasChannel` | `cv:hasChannel` | 아니요 | 서비스를 이용하는 경로 (`Channel`) |
| `hasInputType` | `cv:hasInputType` | 아니요 | 서비스에 필요한 증빙 유형 (`EvidenceType`) |
| `hasLegalResource` | `cv:hasLegalResource` | 아니요 | 서비스의 근거 법령이나 그 하위 단위 (`Work`) |
| `hasPart` | `dct:hasPart` | 아니요 | 하위 서비스 (`PublicService`) |
| `hasParticipation` | `cv:hasParticipation` | 아니요 | 서비스에서 당사자가 맡는 역할 (`Participation`) |
| `holdsRequirement` | `cv:holdsRequirement` | 아니요 | 조건이나 제한 (`Requirement`) |
| `isGroupedBy` | `cv:isGroupedBy` | 아니요 | 서비스를 필요로 하는 사건 (`Event`) |
| `produces` | `cpsv:produces` | 아니요 | 서비스의 결과 (`Output`) |
| `relatedService` | `cv:relatedService` | 아니요 | 관련 서비스 (`PublicService`) |
| `requires` | `dct:requires` | 아니요 | 먼저 거쳐야 하는 서비스 (`PublicService`) |

### PublicOrganisation

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `subOrganizationOf` | `org:subOrganizationOf` | 아니요 | 상위 공공기관 (`PublicOrganisation`) |

### Participation

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `role` | `cv:role` | 예 | 당사자가 맡는 역할이나 당사자 유형 (`Concept`) |
| `hasParticipant` | `cv:hasParticipant` | 아니요 | 역할을 맡는 특정 당사자 (`Agent`) |
| `holdsRequirement` | `cv:holdsRequirement` | 아니요 | 조건이나 제한 (`Requirement`) |

### Channel

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `ownedBy` | `cv:ownedBy` | 아니요 | 경로를 운영하는 공공기관 (`PublicOrganisation`) |

### Rule

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `implements` | `cpsv:implements` | 예 | 규칙의 근거 법령이나 그 하위 단위 (`Work`) |
| `variable` | `employment:variable` | 예 | 규칙이 산출하는 정보 항목 (`InformationConcept`) |
| `appliesWhen` | `employment:appliesWhen` | 아니요 | 규칙이나 조건이 적용되는 조건 (`Requirement`) |
| `requiredInput` | `employment:requiredInput` | 아니요 | 규칙의 입력 정보 항목 (`InformationConcept`) |

- `variable`: DMN 1.3 decision의 variable에 대응한다.
- `appliesWhen`: cpsv:Rule과 cv:Requirement에는 적용 조건을 나타내는 property가 없어서 정의한다. 조건을 모두 충족할 때 적용된다.
- `requiredInput`: DMN 1.3의 requiredInput에 대응한다. FEEL 식에서는 정보 항목 노트의 이름을 변수 이름으로 쓴다.

### Requirement

`Criterion`, `Constraint`에 쓴다.

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `appliesWhen` | `employment:appliesWhen` | 아니요 | 규칙이나 조건이 적용되는 조건 (`Requirement`) |
| `hasConcept` | `cv:hasConcept` | 아니요 | 판단하는 정보 항목 (`InformationConcept`) |
| `hasRequirement` | `cv:hasRequirement` | 아니요 | 하위 조건이나 제한 (`Requirement`) |

- `appliesWhen`: cpsv:Rule과 cv:Requirement에는 적용 조건을 나타내는 property가 없어서 정의한다. 조건을 모두 충족할 때 적용된다.
- `hasRequirement`: 하위 조건이나 제한을 모두 충족할 때 상위 조건이나 제한이 충족된다.
- `hasRequirement`: 하위 사유 중 어느 하나만 충족하면 되는 경우는 사유를 ConceptScheme으로 두고, 정보 항목의 `conformsTo`와 `unaryTests`로 적는다.

### Constraint

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `constrains` | `cv:constrains` | 예 | 제한하는 정보 항목 (`InformationConcept`) |

### InformationConcept

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `conformsTo` | `dct:conformsTo` | 아니요 | 값으로 쓸 수 있는 코드 체계 (`ConceptScheme`) |

### EvidenceType

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `isDefinedBy` | `rdfs:isDefinedBy` | 아니요 | 증빙 유형을 정한 별지 서식 (`Work`) |

### LegalResource

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `typeDocument` | `eli:type_document` | 예 | 법률, 대통령령, 부령, 고시 같은 법령 종류 (`Concept`) |

### LegalResourceSubdivision

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `isPartOf` | `eli:is_part_of` | 예 | 속한 상위 단위 (`Work`) |

### Concept

| 이름 | 표준 | 필수 | 대상 |
| --- | --- | --- | --- |
| `inScheme` | `skos:inScheme` | 예 | 속한 용어집이나 코드 체계 (`ConceptScheme`) |
| `broader` | `skos:broader` | 아니요 | 상위 개념 (`Concept`) |
| `related` | `skos:related` | 아니요 | 관련 개념 (`Concept`) |

## Datatype properties

값이나 block IRI를 담는 class별 property다. 배치 기준은 Object properties와 같다.

### Rule

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `decisionTable` | `employment:decisionTable` | 아니요 | 규칙의 결정표 (`DecisionTable`) |
| `literalExpression` | `employment:literalExpression` | 아니요 | 규칙의 FEEL 식 |

### Requirement

`Criterion`, `Constraint`에 쓴다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `hasEvidenceTypeList` | `cv:hasEvidenceTypeList` | 아니요 | 조건을 증명하는 증빙 유형 목록 (`EvidenceTypeList`) |
| `isDerivedFrom` | `cv:isDerivedFrom` | 아니요 | 조건이나 제한의 근거가 된 block |
| `unaryTests` | `employment:unaryTests` | 아니요 | 정보 항목의 값이 충족해야 하는 FEEL unary tests |

- `hasEvidenceTypeList`: 목록이 여럿이면 그중 하나를 충족하면 된다.
- `unaryTests`: CCCEV에는 값의 조건을 적는 property가 없어서 정의한다. `>= 180`, `<= 113500`, `>= date("2026-01-01")`처럼 적는다.
- `unaryTests`: 여러 정보 항목에 걸친 조건은 정보 항목마다 하위 조건으로 나눈다.

### InformationConcept

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `typeRef` | `employment:typeRef` | 예 | FEEL 자료형 |
| `currency` | `sdo:currency` | 아니요 | ISO 4217 통화 코드 |
| `unitCode` | `sdo:unitCode` | 아니요 | UN/CEFACT 단위 코드 |

- `typeRef`: DMN 1.3의 typeRef에 대응한다.
- `unitCode`: 일은 DAY, 주는 WEE, 월은 MON, 년은 ANN, 시간은 HUR다.

### Work

`LegalResource`, `LegalResourceSubdivision`에 쓴다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `basedOn` | `eli:based_on` | 아니요 | 위임한 상위 법령이나 그 block |
| `cites` | `eli:cites` | 아니요 | 본문이 인용하는 법령이나 그 block |
| `idLocal` | `eli:id_local` | 아니요 | 법제처 식별자 |
| `isRealizedBy` | `eli:is_realized_by` | 아니요 | 시행일 버전 목록 (`LegalExpression`) |
| `title` | `dct:title` | 아니요 | 법령명이나 조문 제목 |

- `idLocal`: 법령은 법령ID, 행정규칙은 행정규칙ID, 버전은 법령일련번호(MST)나 행정규칙일련번호다.

### LegalResourceSubdivision

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `typeSubdivision` | `eli:type_subdivision` | 예 | 하위 단위의 종류: `chapter`(장), `section`(절), `article`(조), `paragraph`(항), `point`(호), `subpoint`(목), `lead`(각 호 외의 부분), `annex`(별표), `remarks`(별표의 비고), `preamble`(고시의 개정문), `form`(별지 서식), `addendum`(부칙) |
| `number` | `eli:number` | 아니요 | 제40조, 제1항, 별표 1 같은 하위 단위 번호 |

### Concept

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `exactMatch` | `skos:exactMatch` | 아니요 | 다른 체계의 같은 개념 |
| `notation` | `skos:notation` | 아니요 | 코드 값 |

## Note documents

instance가 아니라 wiki 노트 자체를 설명하는 property다.

`NoteDocument`(`foaf:Document`): wiki 노트 자체

- 노트 하나는 instance 하나를 설명하고, 출처와 편집 상태는 노트에 붙는다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `identifier` | `dct:identifier` | 예 | instance의 identifier 뒤에 -note를 붙인 식별자 |
| `primaryTopic` | `foaf:primaryTopic` | 예 | 노트가 설명하는 instance (`NamedThing`) |
| `source` | `dct:source` | 예 | 노트가 근거로 삼은 block, 원문, 인용 |
| `status` | `sdo:creativeWorkStatus` | 예 | 노트의 편집 상태: `draft`(LLM이 만들거나 고친 상태), `verified`(별도 agent나 생성 스크립트가 원문과 대조한 상태), `reviewed`(사람이 승인한 상태) |
| `reviewedBy` | `sdo:reviewedBy` | 아니요 | 승인한 사람의 IRI (uri) |
| `lastReviewed` | `sdo:lastReviewed` | 아니요 | 승인일 (date) |

- `identifier`: instance의 IRI는 base IRI 뒤에 identifier를 붙여 만든다.

## Statute versions

법령 노트의 시행일 버전이다. 법령 노트의 `isRealizedBy` 안에 적는다.

`LegalExpression`(`eli:LegalExpression`): 법령이나 그 하위 단위의 시행일 버전 하나

- 같은 시행일자에 법령일련번호(MST)가 여럿이면 공포일자가, 그다음 공포번호가 늦은 버전을 쓴다.
- identifier는 실현하는 Work의 identifier 뒤에 -v<시행일자>를 붙인다. block 버전은 노트의 block ID를 그대로 붙여 law-001761-art-45-v20260918-p5처럼 쓰고, law-001761-art-45-p5를 실현한다.
- 시행일자는 그 단위가 이 본문을 처음 가진 법령 버전의 시행일자다.
- 버전 사이의 포함 관계는 실현하는 Work의 `isPartOf`로 나타낸다. ELI 1.4의 eli:is_part_of는 Work에만 쓴다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `identifier` | `dct:identifier` | 예 | 버전의 kebab-case 식별자 |
| `realizes` | `eli:realizes` | 예 | 이 버전이 실현하는 법령이나 하위 단위 (`Work`) |
| `firstDateEntryInForce` | `eli:first_date_entry_in_force` | 예 | 버전의 시행일자 (date) |
| `dateNoLongerInForce` | `eli:date_no_longer_in_force` | 아니요 | 버전이 시행되는 마지막 날 (date) |
| `datePublication` | `eli:date_publication` | 아니요 | 공포일자나 발령일자 (date) |
| `idLocal` | `eli:id_local` | 아니요 | 법령일련번호(MST)나 행정규칙일련번호 |
| `number` | `eli:number` | 아니요 | 공포번호나 발령번호 |
| `text` | `sdo:text` | 아니요 | 정규화한 block 본문 |
| `wasDerivedFrom` | `prov:wasDerivedFrom` | 아니요 | 이 버전을 만든 원문 (`Entity`) |

- `identifier`: instance의 IRI는 base IRI 뒤에 identifier를 붙여 만든다.
- `idLocal`: 법령은 법령ID, 행정규칙은 행정규칙ID, 버전은 법령일련번호(MST)나 행정규칙일련번호다.

## Inline structures

다른 instance의 property 안에 inline으로 적는 구조다. 배치 기준은 Object properties와 같다.

### EvidenceTypeList

`EvidenceTypeList`(`cv:EvidenceTypeList`): 함께 내야 하는 증빙 유형의 목록

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `specifiesEvidenceType` | `cv:specifiesEvidenceType` | 예 | 목록에 든 증빙 유형 (`EvidenceType`) |

- `specifiesEvidenceType`: 목록에 든 증빙 유형이 모두 필요하다.

### DecisionTable

`DecisionTable`(`employment:DecisionTable`): Rule의 결정표

- DMN 1.3의 tDecisionTable에 대응한다. DMN은 XML schema만 공개하고 RDF 어휘가 없어서 `employment:` 이름공간에 둔다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `hitPolicy` | `employment:hitPolicy` | 예 | 여러 행이 맞을 때의 처리 방식: `UNIQUE`(맞는 행이 하나뿐이어야 함), `FIRST`(맞는 행 중 첫 번째 행의 결과), `ANY`(맞는 행들의 결과가 모두 같아야 함) |
| `input` | `employment:input` | 예 | 입력 열 목록 (`InputClause`) |
| `output` | `employment:output` | 예 | 출력 열 목록 (`OutputClause`) |
| `rule` | `employment:rule` | 예 | 행 목록 (`DecisionRule`) |

### InputClause

`InputClause`(`employment:InputClause`): 결정표의 입력 열

- DMN 1.3의 tInputClause에 대응한다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `inputExpression` | `employment:inputExpression` | 예 | 입력 열의 정보 항목 (`InformationConcept`) |
| `position` | `sdo:position` | 예 | 1부터 세는 순서 (integer) |

### OutputClause

`OutputClause`(`employment:OutputClause`): 결정표의 출력 열

- DMN 1.3의 tOutputClause에 대응한다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `name` | `employment:name` | 예 | 출력 열의 정보 항목 (`InformationConcept`) |
| `position` | `sdo:position` | 예 | 1부터 세는 순서 (integer) |

### DecisionRule

`DecisionRule`(`employment:DecisionRule`): 결정표의 한 행

- DMN 1.3의 tDecisionRule에 대응한다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `inputEntry` | `employment:inputEntry` | 예 | 입력 칸 목록 (`UnaryTests`) |
| `outputEntry` | `employment:outputEntry` | 예 | 출력 칸 목록 (`LiteralExpression`) |
| `position` | `sdo:position` | 예 | 1부터 세는 순서 (integer) |

### UnaryTests

`UnaryTests`(`employment:UnaryTests`): 결정표 한 칸의 입력 조건

- DMN 1.3의 tUnaryTests에 대응한다. `position`은 같은 위치의 입력 열을 가리킨다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `position` | `sdo:position` | 예 | 1부터 세는 순서 (integer) |
| `text` | `sdo:text` | 예 | FEEL unary tests |

### LiteralExpression

`LiteralExpression`(`employment:LiteralExpression`): 결정표 한 칸의 출력 값

- DMN 1.3의 tLiteralExpression에 대응한다. `position`은 같은 위치의 출력 열을 가리킨다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `position` | `sdo:position` | 예 | 1부터 세는 순서 (integer) |
| `text` | `sdo:text` | 예 | FEEL 식 |

## Raw sources

`raw/` 노트와 그 인용의 property다. 원문은 wiki보다 먼저 존재하므로 wikilink 대신 identifier를 쓴다.

### Entity

`Entity`(`prov:Entity`): `raw/` 노트의 원문 한 건

- identifier는 raw-<출처>-<원문 식별자>-<수집 일시>다. 법령은 raw-law-001761-20260918-284449-20261015t1030처럼 쓴다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `identifier` | `dct:identifier` | 예 | 바뀌지 않는 kebab-case 식별자 |
| `title` | `dct:title` | 예 | 법령명이나 조문 제목 |
| `publisher` | `dct:publisher` | 예 | 원문을 공개한 기관 (`PublicOrganisation`) |
| `url` | `sdo:url` | 예 | 수집한 주소 (uri) |
| `generatedAtTime` | `prov:generatedAtTime` | 예 | 수집 일시 (datetime) |
| `sha256` | `spdx:checksumValue` | 예 | 정규화한 본문의 SHA-256 hash |
| `license` | `dct:license` | 예 | 이용 조건 |
| `modified` | `dct:modified` | 아니요 | 원문이 밝힌 최종 수정일 (date) |
| `hasPart` | `dct:hasPart` | 아니요 | Git에 남기는 짧은 인용 (`Quotation`) |

- `identifier`: instance의 IRI는 base IRI 뒤에 identifier를 붙여 만든다.
- `url`: 인증값 parameter는 지우고 저장한다.

### Quotation

`Quotation`(`sdo:Quotation`): 원문을 Git에 두지 않는 출처에서 인용한 짧은 문장

- 저작권법 제28조의 범위에서 출처를 밝혀 인용한다.

| 이름 | 표준 | 필수 | 값 |
| --- | --- | --- | --- |
| `identifier` | `dct:identifier` | 예 | 바뀌지 않는 kebab-case 식별자 |
| `text` | `sdo:text` | 예 | 본문 |
| `sha256` | `spdx:checksumValue` | 예 | 정규화한 본문의 SHA-256 hash |

- `identifier`: instance의 IRI는 base IRI 뒤에 identifier를 붙여 만든다.
