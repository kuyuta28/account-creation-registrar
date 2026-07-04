# Registrar - Ch?y Local (Không Docker)

## Lý do không dùng Docker

Docker t?o ra nhi?u v?n d? cho browser automation:
- **Browser binaries**: Permission, missing libraries
- **X11/Display**: C?n X Server bên ngoài d? hi?n th? browser
- **Dependencies**: GTK, system libraries ph?c t?p
- **Build ch?m**: M?i s?a d?i c?n rebuild 2-3 phút

## Setup Local

### 1. Cài d?t dependencies

`powershell
cd D:\business\account-creation\registrar
pip install -e ".[dev]"
`

### 2. Cài d?t browsers

`powershell
playwright install chromium
patchright install chromium
`

### 3. C?u hình environment

T?o file .env trong thu m?c egistrar/:

`
DATABASE_URL=postgresql+asyncpg://ccs:ccs_secret@localhost:5432/account_creator
`

### 4. Ch?y API server

`powershell
cd D:\business\account-creation\registrar
python run_api.py
`

Server s? ch?y t?i http://localhost:8709

## Luu ý

- **Headless mode**: Set headless: true trong config/config.yaml d? ch?y không c?n display
- **Non-headless**: Browser s? hi?n th? trên Windows, không c?n X Server
- **Database**: PostgreSQL ph?i ch?y (có th? dùng Docker cho DB thôi)

## API Endpoints

- GET /api/v1/health - Health check
- GET /api/v1/registration/services - Danh sách services h? tr?
- POST /api/v1/registration/jobs - T?o registration job
- GET /api/v1/accounts/services - Danh sách services trong DB
