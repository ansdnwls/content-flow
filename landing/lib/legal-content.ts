export type LegalSection = {
  title: string;
  body: string[];
  bullets?: string[];
};

export type LegalDocument = {
  title: string;
  summary: string;
  intro: string[];
  sections: LegalSection[];
  footnote: string;
};

export const LEGAL_LAST_UPDATED = "April 8, 2026";

export const legalNavigation = [
  { href: "/legal/privacy", label: "Privacy Policy" },
  { href: "/legal/cookies", label: "Cookie Policy" },
  { href: "/legal/terms", label: "Terms of Service" },
  { href: "/legal/dpa", label: "DPA Template" },
  { href: "/legal/subprocessors", label: "Sub-processors" },
] as const;

export const privacyDocument: LegalDocument = {
  title: "Privacy Policy / 개인정보 처리방침",
  summary:
    "How ContentFlow collects, uses, stores, exports, and deletes personal information under GDPR and CCPA baselines.",
  intro: [
    "ContentFlow processes account, publishing, analytics, billing, and support data to operate the service. We apply this policy to users, prospects, and customer representatives who interact with the API, dashboard, or landing site.",
    "ContentFlow는 API, 대시보드, 랜딩 페이지를 통해 수집되는 계정 정보, 게시 이력, 분석 데이터, 결제 정보, 지원 문의 정보를 서비스 제공 목적 범위 내에서 처리합니다.",
  ],
  sections: [
    {
      title: "1. Categories of data / 수집하는 정보 범주",
      body: [
        "We may collect contact details, authentication identifiers, workspace metadata, publishing content, analytics summaries, billing records, support messages, and security logs.",
        "수집 항목에는 연락처 정보, 인증 식별자, 워크스페이스 메타데이터, 게시 콘텐츠, 분석 요약, 결제 기록, 지원 문의, 보안 로그가 포함될 수 있습니다.",
      ],
      bullets: [
        "Account profile, email, full name, workspace metadata",
        "OAuth-connected social account identifiers and encrypted tokens",
        "Posts, videos, comments, analytics snapshots, webhook deliveries",
        "Billing and subscription records required for accounting and fraud prevention",
      ],
    },
    {
      title: "2. Purposes of processing / 처리 목적",
      body: [
        "We use personal data to authenticate users, provide cross-platform publishing workflows, secure the service, support billing, respond to incidents, and improve product quality where consent or legitimate interest applies.",
        "개인정보는 사용자 인증, 멀티 플랫폼 발행 기능 제공, 서비스 보안 유지, 과금 처리, 사고 대응, 동의 또는 정당한 이익 범위 내 제품 개선 목적으로 사용됩니다.",
      ],
    },
    {
      title: "3. Legal bases / 처리의 법적 근거",
      body: [
        "ContentFlow relies on contract necessity, legitimate interests, legal obligations, and explicit consent depending on the processing activity.",
        "ContentFlow는 처리 목적에 따라 계약 이행 필요성, 정당한 이익, 법적 의무, 명시적 동의를 법적 근거로 사용합니다.",
      ],
    },
    {
      title: "4. International transfers / 국외 이전",
      body: [
        "Data may be processed in jurisdictions where our infrastructure providers operate, including the United States. We use contracts, technical safeguards, and processor controls to reduce transfer risk.",
        "데이터는 미국 등 인프라 제공자가 운영되는 국가에서 처리될 수 있으며, 계약적 장치와 기술적 보호조치를 통해 이전 리스크를 낮춥니다.",
      ],
    },
    {
      title: "5. Retention / 보유 기간",
      body: [
        "Retention periods follow service and legal needs. Short-lived operational logs are removed automatically; some financial and audit records are retained longer to meet statutory requirements.",
        "보유 기간은 서비스 운영과 법적 의무를 기준으로 정해집니다. 단기 운영 로그는 자동 삭제되며, 회계 및 감사 기록은 법령상 필요 기간 동안 더 오래 보관될 수 있습니다.",
      ],
      bullets: [
        "Audit logs: 1 year",
        "Email logs: 90 days",
        "Webhook deliveries: 30 days",
        "Deleted-user grace period: 14 days before anonymization",
        "Payment records: up to 7 years where legally required",
      ],
    },
    {
      title: "6. Your rights / 정보주체의 권리",
      body: [
        "Depending on your location, you may request access, correction, deletion, portability, processing restriction, or objection. The dashboard privacy APIs are designed to support these requests.",
        "거주 지역에 따라 열람, 정정, 삭제, 이동권, 처리 제한, 이의제기 권리를 행사할 수 있으며, 대시보드의 개인정보 API가 이를 지원하도록 설계되어 있습니다.",
      ],
    },
    {
      title: "7. Contact / 문의처",
      body: [
        "Privacy or data protection requests may be sent to support@contentflow.dev. We may ask for additional verification before fulfilling sensitive requests.",
        "개인정보 및 데이터 보호 관련 요청은 support@contentflow.dev 로 접수할 수 있으며, 민감한 요청은 추가 본인 확인 후 처리될 수 있습니다.",
      ],
    },
  ],
  footnote:
    "Template notice: this policy is a product template based on GDPR/CCPA baseline requirements. Final legal review and jurisdiction-specific adjustments should be completed separately by company counsel.",
};

export const cookieDocument: LegalDocument = {
  title: "Cookie Policy / 쿠키 정책",
  summary:
    "How ContentFlow uses cookies, local storage, and similar technologies for service continuity and measurement.",
  intro: [
    "ContentFlow uses cookies and similar browser storage to maintain sign-in state, remember product preferences, and measure usage when permitted.",
    "ContentFlow는 로그인 상태 유지, 제품 설정 저장, 허용된 범위 내 사용 분석을 위해 쿠키와 유사 저장 기술을 사용합니다.",
  ],
  sections: [
    {
      title: "1. Essential cookies / 필수 쿠키",
      body: [
        "Essential cookies are required for authentication, security checks, fraud prevention, language routing, and core dashboard behavior.",
        "필수 쿠키는 인증, 보안 점검, 부정 사용 방지, 언어 라우팅, 핵심 대시보드 동작을 위해 필요합니다.",
      ],
    },
    {
      title: "2. Functional cookies / 기능 쿠키",
      body: [
        "Functional cookies remember theme, locale, navigation preferences, and similar convenience settings.",
        "기능 쿠키는 테마, 언어, 탐색 선호도 등 사용자 편의 설정을 기억합니다.",
      ],
    },
    {
      title: "3. Analytics cookies / 분석 쿠키",
      body: [
        "Analytics cookies or local signals may be used to understand page performance, feature adoption, and reliability trends after consent.",
        "분석 쿠키 또는 유사 신호는 동의 이후 페이지 성능, 기능 사용률, 안정성 추세를 이해하기 위해 사용될 수 있습니다.",
      ],
    },
    {
      title: "4. Managing consent / 동의 관리",
      body: [
        "The dashboard cookie banner stores your preference locally and prompts again after one year. You can update your choice from the product when controls are available.",
        "대시보드 쿠키 배너는 사용자의 선택을 로컬에 저장하고 1년 후 다시 동의를 요청합니다. 제품 내 설정에서 추후 선택을 변경할 수 있습니다.",
      ],
    },
  ],
  footnote:
    "Template notice: this cookie policy is a baseline operational template. Separate legal review is recommended before production launch in each target jurisdiction.",
};

export const termsDocument: LegalDocument = {
  title: "Terms of Service / 이용약관",
  summary:
    "Baseline commercial terms for access to the ContentFlow API, dashboard, and related hosted features.",
  intro: [
    "These terms govern access to ContentFlow software, hosted APIs, dashboard features, and related documentation.",
    "본 약관은 ContentFlow 소프트웨어, 호스팅 API, 대시보드 기능, 관련 문서에 대한 접근과 이용을 규율합니다.",
  ],
  sections: [
    {
      title: "1. Service scope / 서비스 범위",
      body: [
        "ContentFlow provides software tooling for content orchestration, publishing workflows, AI-assisted features, analytics, and connected account management.",
        "ContentFlow는 콘텐츠 오케스트레이션, 발행 워크플로우, AI 보조 기능, 분석, 연결 계정 관리를 위한 소프트웨어를 제공합니다.",
      ],
    },
    {
      title: "2. Customer responsibilities / 고객 책임",
      body: [
        "Customers are responsible for credentials, connected platform permissions, lawfulness of uploaded content, and compliance with third-party platform rules.",
        "고객은 자격 증명 관리, 연결 플랫폼 권한, 업로드 콘텐츠의 적법성, 제3자 플랫폼 규정 준수에 책임을 집니다.",
      ],
    },
    {
      title: "3. Fees and suspension / 요금 및 이용 제한",
      body: [
        "Paid plans may renew automatically unless cancelled. We may suspend access for non-payment, abuse, or security risks.",
        "유료 플랜은 해지 전까지 자동 갱신될 수 있으며, 미납, 남용, 보안 위험이 있는 경우 접근이 제한될 수 있습니다.",
      ],
    },
    {
      title: "4. Intellectual property / 지식재산",
      body: [
        "Customers retain rights in their submitted content. ContentFlow retains rights in the software, documentation, and service improvements unless otherwise agreed.",
        "고객은 제출한 콘텐츠에 대한 권리를 유지하고, 별도 합의가 없는 한 ContentFlow는 소프트웨어, 문서, 서비스 개선물에 대한 권리를 보유합니다.",
      ],
    },
    {
      title: "5. Disclaimer and limitation / 면책 및 책임 제한",
      body: [
        "The service is provided on a commercial best-effort basis subject to applicable law and any signed enterprise agreement. Liability limitations should be tailored in final contracting.",
        "서비스는 관련 법령 및 별도 체결된 엔터프라이즈 계약 범위 내에서 상업적 합리성을 기준으로 제공되며, 최종 계약에서 책임 제한 조항을 구체화해야 합니다.",
      ],
    },
  ],
  footnote:
    "Template notice: these terms are a product draft for operational launch. Final contractual wording should be reviewed by counsel before customer signature.",
};

export const dpaDocument: LegalDocument = {
  title: "Data Processing Agreement Template / 개인정보 처리 위수탁 계약서 초안",
  summary:
    "A baseline DPA template for enterprise customers using ContentFlow as a processor or sub-processor.",
  intro: [
    "This template summarizes standard processor commitments around instructions, confidentiality, security, sub-processing, breach notification, and data subject support.",
    "본 템플릿은 지시 처리, 비밀유지, 보안, 하위 처리자, 침해 통지, 정보주체 요청 지원에 관한 기본 처리자 의무를 요약합니다.",
  ],
  sections: [
    {
      title: "1. Roles / 당사자 역할",
      body: [
        "The customer acts as controller or business, and ContentFlow acts as processor or service provider for hosted functionality.",
        "고객은 controller 또는 business, ContentFlow는 호스팅 기능 제공 범위 내 processor 또는 service provider 역할을 수행합니다.",
      ],
    },
    {
      title: "2. Processing details / 처리 세부사항",
      body: [
        "Processing covers user account administration, multi-platform publishing, analytics support, billing operations, and support communications necessary to perform the service.",
        "처리 범위에는 사용자 계정 관리, 멀티 플랫폼 발행, 분석 지원, 과금 운영, 서비스 수행에 필요한 지원 커뮤니케이션이 포함됩니다.",
      ],
    },
    {
      title: "3. Security commitments / 보안 의무",
      body: [
        "ContentFlow applies access controls, encryption for sensitive secrets, audit logging, input validation, and scheduled retention workflows.",
        "ContentFlow는 접근 통제, 민감 비밀정보 암호화, 감사 로그, 입력 검증, 정기 보존 정책을 적용합니다.",
      ],
    },
    {
      title: "4. Sub-processors / 하위 처리자",
      body: [
        "Approved sub-processors may be used for infrastructure, email delivery, and payment operations. The current list is published separately.",
        "인프라, 이메일 전송, 결제 운영을 위해 승인된 하위 처리자를 사용할 수 있으며, 최신 목록은 별도 페이지에 게시됩니다.",
      ],
    },
    {
      title: "5. Incident and deletion support / 사고 및 삭제 지원",
      body: [
        "ContentFlow will support breach notification, access requests, deletion flows, and return or deletion of data according to the applicable agreement.",
        "ContentFlow는 침해 통지, 열람 요청, 삭제 흐름, 계약 종료 시 데이터 반환 또는 삭제를 지원합니다.",
      ],
    },
  ],
  footnote:
    "Template notice: this DPA page is a commercial placeholder and not a substitute for negotiated legal terms. Company counsel should review before execution.",
};

export const subprocessorsDocument: LegalDocument = {
  title: "Sub-processors / 하위 처리자 목록",
  summary:
    "Third-party service providers that may process customer data on behalf of ContentFlow.",
  intro: [
    "ContentFlow may use sub-processors for infrastructure, billing, communications, and customer support operations.",
    "ContentFlow는 인프라, 과금, 커뮤니케이션, 고객 지원 운영을 위해 하위 처리자를 사용할 수 있습니다.",
  ],
  sections: [
    {
      title: "Current sub-processors / 현재 하위 처리자",
      body: [
        "The list below reflects the current baseline vendor set used in the product and compliance documentation.",
        "아래 목록은 현재 제품 및 컴플라이언스 문서에 반영된 기본 벤더 구성을 기준으로 합니다.",
      ],
      bullets: [
        "Supabase — database, storage, and backend infrastructure — United States",
        "Stripe — payment processing and billing operations — United States",
        "Resend — transactional email delivery — United States",
        "Railway — application hosting and deployment support — United States",
      ],
    },
    {
      title: "Change management / 변경 관리",
      body: [
        "We may update this list as service architecture changes. Material changes should be tracked in enterprise contracting or change notices where required.",
        "서비스 구조 변경 시 본 목록은 업데이트될 수 있으며, 중대한 변경은 필요 시 엔터프라이즈 계약 또는 변경 통지를 통해 관리됩니다.",
      ],
    },
  ],
  footnote:
    "Template notice: this page is an operational sub-processor disclosure draft. Jurisdiction-specific disclosure obligations should be reviewed separately with counsel.",
};
