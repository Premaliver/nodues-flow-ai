-- ============================================================
-- Smart NoDues AI — PostgreSQL Schema
-- Rayat Bahra University — No-Dues Management System
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE user_role AS ENUM (
    'student',
    'accounts',
    'hostel',
    'mess',
    'transport',
    'scholarship',
    'hod',
    'examination',
    'super_admin'
);

CREATE TYPE user_status AS ENUM (
    'active',
    'inactive',
    'suspended',
    'graduated',
    'withdrawn'
);

CREATE TYPE student_category AS ENUM (
    'day_scholar',
    'hosteller',
    'transport_user',
    'scholarship',
    'hosteller_transport',
    'scholarship_hosteller',
    'scholarship_transport',
    'hosteller_scholarship_transport'
);

CREATE TYPE application_status AS ENUM (
    'draft',
    'submitted',
    'in_review',
    'approved',
    'rejected',
    'partially_approved'
);

CREATE TYPE approval_status AS ENUM (
    'pending',
    'in_review',
    'approved',
    'rejected',
    'skipped'
);

CREATE TYPE document_type AS ENUM (
    'semester_fee_receipt',
    'exam_fee_receipt',
    'library_clearance',
    'lab_clearance',
    'scholarship_document',
    'identity_proof',
    'other'
);

CREATE TYPE document_status AS ENUM (
    'pending',
    'verified',
    'rejected',
    'duplicate'
);

CREATE TYPE notification_type AS ENUM (
    'application_submitted',
    'department_approved',
    'department_rejected',
    'application_completed',
    'admit_card_generated',
    'document_verified',
    'document_rejected',
    'reminder',
    'query',
    'system'
);

CREATE TYPE audit_action AS ENUM (
    'create',
    'update',
    'delete',
    'approve',
    'reject',
    'upload',
    'download',
    'login',
    'logout',
    'verify',
    'generate'
);

-- ============================================================
-- TABLES
-- ============================================================

-- 1. USERS — Central user table for all roles
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'student',
    status user_status NOT NULL DEFAULT 'active',
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    profile_image_url TEXT,
    is_email_verified BOOLEAN DEFAULT FALSE,
    is_mfa_enabled BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_created_at ON users(created_at);

-- 2. STUDENTS — Extended student profile
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    roll_number VARCHAR(50) UNIQUE NOT NULL,
    enrollment_number VARCHAR(50) UNIQUE NOT NULL,
    course_name VARCHAR(200) NOT NULL,
    branch VARCHAR(200) NOT NULL,
    current_semester INTEGER NOT NULL CHECK (current_semester BETWEEN 1 AND 12),
    batch_year VARCHAR(9) NOT NULL, -- e.g., "2024-2028"
    admission_year INTEGER NOT NULL,
    category student_category NOT NULL DEFAULT 'day_scholar',
    date_of_birth DATE,
    father_name VARCHAR(200),
    mother_name VARCHAR(200),
    guardian_phone VARCHAR(20),
    guardian_email VARCHAR(255),
    permanent_address TEXT,
    current_address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    pincode VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_students_user_id ON students(user_id);
CREATE INDEX idx_students_roll_number ON students(roll_number);
CREATE INDEX idx_students_enrollment ON students(enrollment_number);
CREATE INDEX idx_students_category ON students(category);
CREATE INDEX idx_students_current_semester ON students(current_semester);
CREATE INDEX idx_students_branch ON students(branch);

-- 3. DEPARTMENTS — University departments
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    role user_role NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default departments
INSERT INTO departments (code, name, description, role, display_order) VALUES
    ('ACC', 'Accounts Department', 'Financial clearance, fee verification', 'accounts', 1),
    ('HOS', 'Hostel Department', 'Hostel accommodation clearance', 'hostel', 2),
    ('MESS', 'Mess Department', 'Mess dues clearance', 'mess', 3),
    ('TRP', 'Transport Department', 'Transport fee clearance', 'transport', 4),
    ('SCH', 'Scholarship Department', 'Scholarship verification', 'scholarship', 5),
    ('HOD', 'Head of Department', 'Academic clearance', 'hod', 6),
    ('EXM', 'Examination Department', 'Final clearance and admit card', 'examination', 7);

-- 4. DEPARTMENT STAFF — Staff members per department
CREATE TABLE department_staff (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    designation VARCHAR(200),
    is_head BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, department_id)
);

CREATE INDEX idx_department_staff_dept ON department_staff(department_id);
CREATE INDEX idx_department_staff_user ON department_staff(user_id);

-- 5. SEMESTERS — Academic semester definitions
CREATE TABLE semesters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    semester_number INTEGER NOT NULL CHECK (semester_number BETWEEN 1 AND 12),
    semester_name VARCHAR(100) NOT NULL,
    academic_year VARCHAR(9) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_current BOOLEAN DEFAULT FALSE,
    is_fee_submission_open BOOLEAN DEFAULT FALSE,
    is_clearance_open BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(semester_number, academic_year)
);

CREATE INDEX idx_semesters_current ON semesters(is_current);
CREATE INDEX idx_semesters_clearance ON semesters(is_clearance_open);

-- 6. NO DUES APPLICATIONS — Main application records
CREATE TABLE no_dues_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_number VARCHAR(50) UNIQUE NOT NULL,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    semester_id UUID NOT NULL REFERENCES semesters(id),
    status application_status NOT NULL DEFAULT 'draft',
    category student_category NOT NULL,
    is_urgent BOOLEAN DEFAULT FALSE,
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_applications_student ON no_dues_applications(student_id);
CREATE INDEX idx_applications_status ON no_dues_applications(status);
CREATE INDEX idx_applications_semester ON no_dues_applications(semester_id);
CREATE INDEX idx_applications_category ON no_dues_applications(category);
CREATE INDEX idx_applications_created ON no_dues_applications(created_at);
CREATE UNIQUE INDEX idx_applications_student_semester
    ON no_dues_applications(student_id, semester_id)
    WHERE deleted_at IS NULL;

-- 7. APPLICATION DEPARTMENTS — Department-wise approval tracking
CREATE TABLE application_departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES no_dues_applications(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id),
    status approval_status NOT NULL DEFAULT 'pending',
    assigned_to UUID REFERENCES users(id),
    remarks TEXT,
    processed_at TIMESTAMP WITH TIME ZONE,
    processed_by UUID REFERENCES users(id),
    display_order INTEGER NOT NULL DEFAULT 0,
    is_required BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(application_id, department_id)
);

CREATE INDEX idx_app_dept_application ON application_departments(application_id);
CREATE INDEX idx_app_dept_department ON application_departments(department_id);
CREATE INDEX idx_app_dept_status ON application_departments(status);
CREATE INDEX idx_app_dept_assigned ON application_departments(assigned_to);

-- 8. DOCUMENTS — Uploaded receipts and documents
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES no_dues_applications(id) ON DELETE CASCADE,
    document_type document_type NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    file_hash VARCHAR(64), -- SHA-256 hash for duplicate detection
    status document_status NOT NULL DEFAULT 'pending',
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_documents_application ON documents(application_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_hash ON documents(file_hash);

-- 9. DOCUMENT VERIFICATIONS — AI verification results
CREATE TABLE document_verifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID UNIQUE NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    is_verified BOOLEAN DEFAULT FALSE,
    confidence_score DECIMAL(5,2) CHECK (confidence_score >= 0 AND confidence_score <= 100),
    extracted_data JSONB, -- Store OCR extracted data
    verification_details JSONB, -- Store detailed verification results
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of_document_id UUID REFERENCES documents(id),
    ai_processed_at TIMESTAMP WITH TIME ZONE,
    human_verified_at TIMESTAMP WITH TIME ZONE,
    human_verified_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_doc_verification_document ON document_verifications(document_id);
CREATE INDEX idx_doc_verification_status ON document_verifications(is_verified);
CREATE INDEX idx_doc_verification_duplicate ON document_verifications(is_duplicate);

-- 10. NOTIFICATIONS — Real-time and stored notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type notification_type NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    data JSONB,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    application_id UUID REFERENCES no_dues_applications(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_read ON notifications(user_id, is_read);
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);
CREATE INDEX idx_notifications_type ON notifications(type);

-- 11. AUDIT LOGS — Complete audit trail
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action audit_action NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- 12. ADMIT CARDS — Generated admit cards
CREATE TABLE admit_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID UNIQUE NOT NULL REFERENCES no_dues_applications(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id),
    semester_id UUID NOT NULL REFERENCES semesters(id),
    card_number VARCHAR(50) UNIQUE NOT NULL,
    pdf_path TEXT NOT NULL,
    qr_code_data TEXT NOT NULL,
    qr_code_path TEXT,
    hmac_signature VARCHAR(128) NOT NULL,
    verification_url TEXT,
    is_downloaded BOOLEAN DEFAULT FALSE,
    downloaded_at TIMESTAMP WITH TIME ZONE,
    download_count INTEGER DEFAULT 0,
    generated_by UUID NOT NULL REFERENCES users(id),
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_admit_cards_application ON admit_cards(application_id);
CREATE INDEX idx_admit_cards_student ON admit_cards(student_id);
CREATE INDEX idx_admit_cards_card_number ON admit_cards(card_number);

-- 13. WORKFLOW CONFIG — Configurable approval workflows
CREATE TABLE workflow_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category student_category NOT NULL,
    department_id UUID NOT NULL REFERENCES departments(id),
    step_order INTEGER NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(category, department_id)
);

CREATE INDEX idx_workflow_category ON workflow_config(category);
CREATE INDEX idx_workflow_department ON workflow_config(department_id);

-- 14. SYSTEM SETTINGS — Global system configuration
CREATE TABLE system_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    setting_type VARCHAR(50) DEFAULT 'string',
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    updated_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- INSERT DEFAULT SYSTEM SETTINGS
-- ============================================================

INSERT INTO system_settings (setting_key, setting_value, setting_type, description, is_public) VALUES
    ('university_name', 'Rayat Bahra University', 'string', 'University display name', true),
    ('app_name', 'Smart NoDues AI', 'string', 'Application display name', true),
    ('support_email', 'support@rayatbahra.edu', 'string', 'Support email address', true),
    ('academic_year', '2025-2026', 'string', 'Current academic year', true),
    ('current_semester', '1', 'integer', 'Current active semester', false),
    ('clearance_open', 'false', 'boolean', 'Is clearance currently open', true),
    ('max_file_size_mb', '16', 'integer', 'Maximum upload file size in MB', false),
    ('allowed_file_types', 'pdf,png,jpg,jpeg,webp', 'string', 'Comma-separated allowed file extensions', false),
    ('jwt_expiry_hours', '2', 'integer', 'JWT token expiry in hours', false),
    ('session_timeout_days', '7', 'integer', 'Session timeout in days', false),
    ('maintenance_mode', 'false', 'boolean', 'Is system in maintenance mode', true),
    ('ai_verification_enabled', 'true', 'boolean', 'Enable AI document verification', false);

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables with updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_students_updated_at
    BEFORE UPDATE ON students
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON no_dues_applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_app_dept_updated_at
    BEFORE UPDATE ON application_departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admit_cards_updated_at
    BEFORE UPDATE ON admit_cards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-generate application number
CREATE OR REPLACE FUNCTION generate_application_number()
RETURNS TRIGGER AS $$
DECLARE
    year_part VARCHAR(4);
    seq_part VARCHAR(8);
BEGIN
    year_part := TO_CHAR(NEW.created_at, 'YYYY');
    seq_part := LPAD(FLOOR(RANDOM() * 99999999)::VARCHAR, 8, '0');
    NEW.application_number := 'ND-' || year_part || '-' || seq_part;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_application_number
    BEFORE INSERT ON no_dues_applications
    FOR EACH ROW
    EXECUTE FUNCTION generate_application_number();

-- ============================================================
-- VIEWS
-- ============================================================

-- Dashboard summary view for students
CREATE VIEW student_dashboard_summary AS
SELECT
    s.id AS student_id,
    s.roll_number,
    u.first_name || ' ' || u.last_name AS full_name,
    s.course_name,
    s.branch,
    s.current_semester,
    s.category,
    COUNT(nda.id) AS total_applications,
    COUNT(CASE WHEN nda.status = 'approved' THEN 1 END) AS approved_applications,
    COUNT(CASE WHEN nda.status = 'submitted' THEN 1 END) AS pending_applications,
    COUNT(CASE WHEN nda.status = 'rejected' THEN 1 END) AS rejected_applications
FROM students s
JOIN users u ON u.id = s.user_id
LEFT JOIN no_dues_applications nda ON nda.student_id = s.id AND nda.deleted_at IS NULL
GROUP BY s.id, s.roll_number, u.first_name, u.last_name, s.course_name, s.branch, s.current_semester, s.category;

-- Application progress view
CREATE VIEW application_progress_view AS
SELECT
    nda.id AS application_id,
    nda.application_number,
    nda.status,
    nda.category,
    s.roll_number,
    s.course_name,
    s.branch,
    u.first_name || ' ' || u.last_name AS student_name,
    sem.semester_number,
    sem.academic_year,
    COUNT(ad.id) AS total_departments,
    COUNT(CASE WHEN ad.status = 'approved' THEN 1 END) AS approved_departments,
    COUNT(CASE WHEN ad.status = 'pending' THEN 1 END) AS pending_departments,
    COUNT(CASE WHEN ad.status = 'rejected' THEN 1 END) AS rejected_departments
FROM no_dues_applications nda
JOIN students s ON s.id = nda.student_id
JOIN users u ON u.id = s.user_id
JOIN semesters sem ON sem.id = nda.semester_id
LEFT JOIN application_departments ad ON ad.application_id = nda.id
GROUP BY nda.id, nda.application_number, nda.status, nda.category, s.roll_number,
         s.course_name, s.branch, u.first_name, u.last_name, sem.semester_number, sem.academic_year;

