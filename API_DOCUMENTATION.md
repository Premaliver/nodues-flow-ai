# Smart NoDues AI — Enterprise B2B API Documentation & Integration Manual

> **Product**: Smart NoDues AI (Automated Multi-Tenant No-Dues Clearance & Digital Admit Card Platform)  
> **Target Audience**: University IT Directors, CTOs, System Integrators, ERP Consultants, Software Engineers  
> **API Version**: `v1.0.0` (OpenAPI 3.0 Compatible)  
> **Authentication**: JWT Bearer Tokens (RFC 7519) + Session Cookies  
> **Security Audit Level**: Grade 3 SHA-256 File Hashes & HMAC-Signed QR Stamps  

---

## 🏛️ Executive Summary & Value Proposition

Smart NoDues AI is an enterprise-grade automated clearance platform engineered to eliminate paper bottlenecks, queue delays, and fraud in university end-of-semester exam roll-number issuing.

### Key Capabilities for University Pitch & Sales:
- **Instant ERP Integration**: Connects seamlessly with SAP Higher Education, ERPNext, CollPoll, Academia ERP, PowerCampus, and custom Student Information Systems (SIS).
- **Sequential Clearance Engine**: Configurable clearance flow enforcing departmental order (Facilities -> Department HOD -> Accounts -> Examination Board).
- **Anti-Fraud Security**: Every generated Admit Card features a cryptographic **HMAC-SHA256 digital signature** and scannable QR verification code.
- **Audit Compliance**: Immutable event trail (`AuditLog`) logging every approval, rejection, document view, and card generation with IP address and timestamp.

---

## 🔌 Live Interactive API Developer Portal

When deployed at a university domain, developers can access live interactive documentation and test endpoints:
- **Interactive Developer Portal**: `https://your-university-domain.edu/api/docs`
- **OpenAPI 3.0 Spec (.json)**: `https://your-university-domain.edu/api/openapi.json`

---

## 🔑 Authentication & Security Architecture

### 1. Authentication Headers
All protected API endpoints require an HTTP `Authorization` header containing a valid JWT access token:

```http
Authorization: Bearer <your_jwt_access_token>
```

### 2. Login & Token Exchange

#### `POST /auth/login`
Authenticates students, staff, or super admins and issues access + refresh tokens.

**Request (JSON)**:
```json
{
  "email": "student@rayatbahra.edu",
  "password": "UserSecretPassword123!",
  "role": "student"
}
```

*Note: Super Admin authenticates using `"username"` instead of `"email"` and setting `"role": "super_admin"`.*

**Response (`200 OK`)**:
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "dashboard_url": "/student/dashboard",
    "user": {
      "id": "u-9842a-1123",
      "email": "student@rayatbahra.edu",
      "full_name": "Rohan Sharma",
      "role": "student"
    }
  }
}
```

---

## 🎓 Student Portal APIs

### 1. Submit No-Dues Application
`POST /student/api/apply`

Submits a new no-dues clearance application for the current academic semester.

**Headers**: `Authorization: Bearer <token>`

**Request (JSON)**:
```json
{
  "semester_id": "c71a3d90-4822-4911-9a72-88229103b41c",
  "category": "hosteller",
  "selected_departments": ["hostel", "mess"],
  "hod_department_id": "dept-hod-civil-id"
}
```

**Response (`201 Created`)**:
```json
{
  "success": true,
  "message": "No-dues application submitted successfully",
  "data": {
    "application_id": "app-8812a-3310",
    "application_number": "ND-2026-F8A2B1C9",
    "status": "submitted",
    "total_steps": 4
  }
}
```

### 2. Student Dashboard Status
`GET /student/api/dashboard`

Retrieves current applications, department clearance progress badges, and issued admit cards for the authenticated student.

---

## 🏢 Department Clearance Staff APIs

*(Applies to Accounts, Hostel, Mess, Transport, Scholarship, HOD)*

### 1. Fetch Department Clearance Queue
`GET /<department_role>/api/dashboard`

Retrieves applications pending approval in the specified department.

### 2. Process Clearance (Approve / Reject)
`POST /<department_role>/api/process/<app_dept_id>`

**Request (JSON)**:
```json
{
  "action": "approved",
  "remarks": "Verified library and fee dues. No outstanding dues found."
}
```

**Response (`200 OK`)**:
```json
{
  "success": true,
  "message": "Clearance approved successfully",
  "data": {
    "app_dept_id": "ad-89123-1102",
    "status": "approved"
  }
}
```

---

## 📝 Examination Board APIs

### 1. List Applications Ready for Admit Cards
`GET /examination/api/dashboard`

**Strict Workflow Enforcement**: Only applications where **ALL preceding departments (Hostel, Mess, Transport, Scholarship, HOD, Accounts)** have `approved` will be listed here.

### 2. Generate HMAC QR Signed Admit Card PDF
`POST /examination/api/generate-admit-card/<application_id>`

Generates the official downloadable PDF with an embedded cryptographic HMAC-SHA256 QR verification badge.

**Response (`201 Created`)**:
```json
{
  "success": true,
  "message": "Admit card generated successfully",
  "data": {
    "card_number": "AC-210492-6-F8A2",
    "student_name": "Rohan Sharma",
    "roll_number": "210492",
    "download_url": "/examination/api/admit-card/AC-210492-6-F8A2/pdf",
    "verification_url": "/verify-admit-card/AC-210492-6-F8A2"
  }
}
```

---

## 🔍 Public Verification API

### Public Scannable QR Verification
`GET /verify-admit-card/<card_number>`

Scannable by exam invigilators, gate security, and official personnel on mobile phones to verify authenticity.

**Response (`200 OK`)**:
```json
{
  "success": true,
  "verified": true,
  "data": {
    "card_number": "AC-210492-6-F8A2",
    "student_name": "Rohan Sharma",
    "roll_number": "210492",
    "course": "B.Tech Computer Science",
    "semester": 6,
    "status": "VALID_OFFICIAL_ISSUED"
  }
}
```

---

## 📈 Super Admin & Intelligence Analytics APIs

### Real-Time System Intelligence
`GET /superadmin/api/analytics?days=30`

Returns system KPIs, daily application trends, user registrations, and department clearance throughput.

**Response (`200 OK`)**:
```json
{
  "success": true,
  "data": {
    "kpi": {
      "total_applications": 1420,
      "approval_rate": 94.2,
      "admit_cards_issued": 1338,
      "total_students": 1500
    },
    "department_performance": [
      { "code": "ACC", "name": "Accounts", "pending": 12, "approved": 1380, "rejected": 8 },
      { "code": "HST", "name": "Hostel", "pending": 4, "approved": 420, "rejected": 2 }
    ]
  }
}
```

---

## 🤝 How to Pitch & Share with Universities

When presenting or emailing this project to University Leadership, IT Teams, or CTOs:

1. **Share the Live API Explorer Link**:  
   `https://<your-server-url>/api/docs`
2. **Provide the OpenAPI Spec**:  
   Share `/api/openapi.json` so their IT engineers can import it into **Postman** or **Swagger**.
3. **Highlight Key Selling Points**:
   - Zero paper costs & 100% digital clearance.
   - Fraud prevention via HMAC-SHA256 scannable QR codes.
   - Plug-and-play REST API compatible with any existing university ERP.
