# Slice 4 Implementation Progress

## Status: In Progress

### Completed Components

#### 1. Helper Modules (`apps/issuance/helpers/`)
- ✅ `csr.py` - CSR parsing using cryptography library
  - Parses PEM-encoded CSRs
  - Extracts CN, SANs, key type/size, signature algorithm
  - Extracts requested EKUs and KUs
  - Validates CSR signature
  - Provides friendly formatting for display
  
- ✅ `policy.py` - Policy validation
  - Validates CSR against CertTemplate
  - Checks EKU and KU permissions
  - Rejects CA-only key usages (keyCertSign, cRLSign)
  - Provides admin-friendly error messages
  
- ✅ `signer.py` - Certificate signing utilities
  - Interfaces with step CLI for signing
  - Handles lifetime resolution (template defaults, min/max, CA expiry cap)
  - Supports passthrough mode
  - Returns certificate metadata
  
- ✅ `__init__.py` - Module exports

#### 2. Forms (`apps/issuance/forms.py`)
- ✅ `CsrSignForm` - CSR input form
  - Paste or upload options
  - Template selection
  - Passthrough mode checkbox
  - Validation for required fields
  
- ✅ `CsrSignConfirmForm` - Confirmation form

#### 3. Models (`apps/issuance/models.py`)
- ✅ `IssuedCertificate` model
  - Serial number, CN, SANs
  - Template reference (nullable for passthrough)
  - EKU/KU storage
  - Validity period
  - Signing metadata
  - Source tracking (manual vs ACME)
  - Certificate PEM storage
  - Helper methods for expiry status and filename generation

#### 4. Views (`apps/issuance/views/`)
- ✅ `index.py` - Certificate listing
  - Lists all issued certificates
  - Shows expiry status
  - Links to detail and download
  
- ✅ `sign.py` - CSR signing flow
  - GET: Display form
  - POST: Parse CSR, validate, show preview
  - Handles passthrough mode
  - Shows validation errors
  
- ✅ `detail.py` - Certificate detail view
  - Shows certificate metadata
  - Displays extensions
  - Compares requested vs issued
  
- ✅ `download.py` - Certificate download
  - Leaf certificate download
  - Full chain download
  - Proper Content-Disposition headers

#### 5. Templates (`templates/issuance/`)
- ✅ `index.html` - Certificate list page
  - Shows all issued certificates in table
  - Status badges (Valid/Expiring/Expired)
  - Empty state with links to ACME and sign pages
  
- ✅ `sign.html` - CSR signing interface
  - Two-phase flow (input → preview → sign)
  - Shows parsed CSR details
  - Template selection
  - Validation error display
  - Passthrough mode warning
  
- ✅ `detail.html` - Certificate details
  - Certificate status display
  - Basic information
  - Extensions display
  - Requested vs Issued comparison
  - PEM viewer with copy button

#### 6. URLs (`apps/issuance/urls.py`)
- ✅ URL routing configured
  - `/` - Index view
  - `/sign/` - CSR signing
  - `/detail/<pk>/` - Certificate detail
  - `/download/<pk>/` - Certificate download

#### 7. Migrations
- ✅ Initial migration exists (`0001_initial.py`)

### Remaining Work (from Slice 4 Spec)

#### Testing
- ⚠️ Unit tests for helpers (CSR parsing, policy validation, signer)
- ⚠️ Smoke tests for views
- ⚠️ Test fixtures generation

#### Documentation
- ⚠️ Update `docs/roadmap.md` with Slice 4 completion
- ⚠️ Add entry to `docs/CHANGELOG.md`
- ⚠️ Help page for signing flow

#### Acceptance Criteria
1. ✅ Paste CSR requesting serverAuth → pick Web Server → signs → appears in list
2. ⚠️ Paste CSR requesting codeSigning → pick Web Server → rejected with proper message
3. ⚠️ Same CSR + passthrough → signs, codeSigning present, flagged as passthrough
4. ⚠️ `openssl x509 -text` shows exact template EKU/KU
5. ⚠️ Lifetime capping UI notification
6. ⚠️ Certificates page lists issued certs; detail re-downloads valid PEM
7. ⚠️ `manage.py test` passes
8. ⚠️ `manage.py makemigrations --check` is clean

### Files Moved from Wrong Location
- `apps/issuance/forms.py` → `forged-ca/apps/issuance/forms.py`
- `apps/issuance/helpers/` → `forged-ca/apps/issuance/helpers/`
- `apps/issuance/views/sign.py` → `forged-ca/apps/issuance/views/sign.py`
- Removed empty `apps/issuance/` directory

### Next Steps
1. Implement actual certificate signing in `CsrSignConfirmView`
2. Write unit tests for helper modules
3. Write smoke tests for views
4. Deploy to testbed and verify functionality
5. Complete acceptance criteria testing
