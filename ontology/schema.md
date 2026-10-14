# 온톨로지 스키마

클래스와 속성은 공공서비스·법령·용어 표준의 이름을 그대로 쓴다. frontmatter 키마다 표준 IRI가 대응하므로 노트를 RDF로 옮길 수 있다. 표준에 없는 개념이 필요하면 이 문서에 먼저 정의하고 이유를 적는다.

## 기준 표준

| 접두어 | 표준 | IRI |
|---|---|---|
| `cpsv` | CPSV-AP 3.2.0 (Core Public Service Vocabulary Application Profile) | `http://purl.org/vocab/cpsv#` |
| `cv` | CPSV-AP·CCCEV 2.1.0 (Core Criterion and Core Evidence Vocabulary) | `http://data.europa.eu/m8g/` |
| `eli` | ELI (European Legislation Identifier) | `http://data.europa.eu/eli/ontology#` |
| `skos` | SKOS | `http://www.w3.org/2004/02/skos/core#` |
| `dct` | DCMI Metadata Terms | `http://purl.org/dc/terms/` |
| `adms` | ADMS | `http://www.w3.org/ns/adms#` |
| `org` | W3C Organization Ontology | `http://www.w3.org/ns/org#` |
| `dcat` | DCAT | `http://www.w3.org/ns/dcat#` |
| `schema` | Schema.org | `https://schema.org/` |
| `foaf` | FOAF | `http://xmlns.com/foaf/0.1/` |

## 클래스

| `type` | 표준 | 뜻 | 예 |
|---|---|---|---|
| `PublicService` | `cpsv:PublicService` | 공공기관이 제공하는 서비스. 급여와 신청 절차를 포함한다 | 구직급여, 실업인정, 구직신청 |
| `LifeEvent` | `cv:LifeEvent` | 공공서비스가 필요해지는 개인의 사건 | 퇴사, 재취업 |
| `BusinessEvent` | `cv:BusinessEvent` | 공공서비스가 필요해지는 사업장의 사건 | 근로자 퇴사 처리 |
| `PublicOrganisation` | `cv:PublicOrganisation` | 공공기관 | 고용노동부, 고용센터, 근로복지공단 |
| `Channel` | `cv:Channel` | 서비스를 이용하는 경로 | 고용24 누리집, 고용센터 방문 |
| `Criterion` | `cv:Criterion` | 서비스를 받으려면 충족해야 하는 조건 | 피보험단위기간 180일 이상 |
| `Constraint` | `cv:Constraint` | 정보 값에 거는 제한. 기한, 상한, 하한을 포함한다 | 수급기간 12개월 |
| `InformationConcept` | `cv:InformationConcept` | 조건이 판단하는 정보 항목 | 피보험단위기간, 이직일, 이직사유 |
| `EvidenceType` | `cv:EvidenceType` | 증빙 서류의 유형 | 이직확인서 |
| `Output` | `cv:Output` | 서비스가 만들어 내는 결과 | 수급자격 인정 |
| `Rule` | `cpsv:Rule` | 서비스가 따르는 산정·판단 규칙 | 소정급여일수 산정 |
| `LegalResource` | `eli:LegalResource` | 법률, 시행령, 시행규칙, 고시 | 고용보험법 |
| `LegalResourceSubdivision` | `eli:LegalResourceSubdivision` | 조문, 별표 | 고용보험법 제40조 |
| `Concept` | `skos:Concept` | 용어, 코드 값, 대상자 유형 | 피보험자, 상실사유 코드 |
| `ConceptScheme` | `skos:ConceptScheme` | 용어집, 코드 체계 | 고용보험 상실사유 코드 |
| `Dataset` | `dcat:Dataset` | 통계와 데이터셋 | 구직급여 수급 현황 |

합성데이터에만 쓰는 클래스는 `Person`(`foaf:Person`)과 `Evidence`(`cv:Evidence`)다. 실제 개인과 실제 서류는 위키에 두지 않는다.

## 공통 속성

모든 `wiki/` 노트에 쓴다.

| 키 | 표준 | 필수 | 값 |
|---|---|---|---|
| `type` | `rdf:type` | 예 | 위 클래스 중 하나 |
| `identifier` | `dct:identifier` | 예 | 영어 소문자와 하이픈. 법령은 아래 규칙을 따른다 |
| `aliases` | `skos:altLabel` | | 다른 이름 목록 |
| `definition` | `skos:definition` | 예 | 한 문장 정의 |
| `source` | `dct:source` | 예 | 원문 노트 또는 조문 노트 링크 |
| `status` | `adms:status` | 예 | `draft`, `reviewed`, `deprecated` |
| `validFrom` | `schema:validFrom` | | 적용 시작일 `YYYY-MM-DD` |
| `validThrough` | `schema:validThrough` | | 적용 종료일 `YYYY-MM-DD` |
| `reviewedBy` | `schema:reviewedBy` | | 검토자 |
| `lastReviewed` | `schema:lastReviewed` | | 검토일 `YYYY-MM-DD` |
| `isReplacedBy` | `dct:isReplacedBy` | | 대체 노트 링크 |

법령 `identifier`는 법제처 식별자로 만든다. `LegalResource`는 `law-<법령ID>`, `LegalResourceSubdivision`은 `law-<법령ID>-<조문번호 6자리>`다. 예: 제40조는 `law-<법령ID>-004000`이다.

## 관계 속성

각 관계는 이 표의 방향으로만 적는다.

### PublicService

| 키 | 표준 | 필수 | 대상 |
|---|---|---|---|
| `hasCompetentAuthority` | `cv:hasCompetentAuthority` | 예 | `PublicOrganisation` |
| `hasChannel` | `cv:hasChannel` | | `Channel` |
| `holdsRequirement` | `cv:holdsRequirement` | | `Criterion`, `Constraint` |
| `hasInputType` | `cv:hasInputType` | | `EvidenceType` |
| `produces` | `cpsv:produces` | | `Output` |
| `follows` | `cpsv:follows` | | `Rule` |
| `hasLegalResource` | `cv:hasLegalResource` | | `LegalResource`, `LegalResourceSubdivision` |
| `requires` | `dct:requires` | | 먼저 거쳐야 하는 `PublicService` |
| `relatedService` | `cv:relatedService` | | 관련 `PublicService` |
| `isGroupedBy` | `cv:isGroupedBy` | | `LifeEvent`, `BusinessEvent` |
| `audience` | `dct:audience` | | 대상자 유형 `Concept` |

### Criterion, Constraint

| 키 | 표준 | 필수 | 대상 |
|---|---|---|---|
| `isDerivedFrom` | `cv:isDerivedFrom` | 예 | 근거 `LegalResourceSubdivision` |
| `hasConcept` | `cv:hasConcept` | | 판단하는 `InformationConcept` |
| `constrains` | `cv:constrains` | | 제한하는 `InformationConcept`. `Constraint`에만 쓴다 |
| `hasRequirement` | `cv:hasRequirement` | | 하위 `Criterion`, `Constraint` |
| `hasEvidenceTypeList` | `cv:hasEvidenceTypeList` | | `EvidenceType` |

CCCEV는 `hasEvidenceTypeList`가 증빙 유형 목록(`cv:EvidenceTypeList`)을 가리키게 한다. 이 위키에서는 목록을 따로 노트로 만들지 않고 증빙 유형을 바로 적는다. 적은 증빙은 모두 필요하다는 뜻이다. 서로 대신할 수 있는 증빙 조합이 있으면 조합마다 `Criterion`을 나눈다.

### Rule

| 키 | 표준 | 필수 | 대상 |
|---|---|---|---|
| `implements` | `cpsv:implements` | 예 | `LegalResource`, `LegalResourceSubdivision` |

### LegalResource, LegalResourceSubdivision

| 키 | 표준 | 필수 | 대상 |
|---|---|---|---|
| `typeDocument` | `eli:type_document` | 예 | 법률, 대통령령, 부령, 고시 같은 법령 종류 `Concept`. `LegalResource`에만 쓴다 |
| `basedOn` | `eli:based_on` | | 위임한 상위 `LegalResource`. 예: 시행령은 법률에 근거한다 |
| `isPartOf` | `eli:is_part_of` | 예 | 조문이 속한 `LegalResource`. `LegalResourceSubdivision`에만 쓴다 |
| `cites` | `eli:cites` | | 본문에서 인용하는 다른 조문 |

조문 노트는 현행 시행본을 기준으로 쓴다. `validFrom`에는 그 시행본의 시행일을 적는다. 항·호·목은 노트를 나누지 않고 본문의 제목(`## 제1항`)으로 둔다.

### PublicOrganisation, Channel

| 키 | 표준 | 필수 | 대상 |
|---|---|---|---|
| `subOrganizationOf` | `org:subOrganizationOf` | | 상위 `PublicOrganisation` |
| `ownedBy` | `cv:ownedBy` | | `Channel`을 운영하는 `PublicOrganisation` |

### Concept, ConceptScheme

| 키 | 표준 | 필수 | 대상 |
|---|---|---|---|
| `inScheme` | `skos:inScheme` | 예 | `ConceptScheme`. `Concept`에만 쓴다 |
| `notation` | `skos:notation` | | 코드 값 |
| `broader` | `skos:broader` | | 상위 `Concept` |
| `related` | `skos:related` | | 관련 `Concept` |
| `exactMatch` | `skos:exactMatch` | | 다른 체계의 같은 개념 |

### Dataset

| 키 | 표준 | 필수 | 대상 |
|---|---|---|---|
| `publisher` | `dct:publisher` | 예 | 공개 기관 `PublicOrganisation` |
