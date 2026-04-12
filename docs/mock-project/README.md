# Mock Project for Testing

This is a sample monorepo project for testing OpenOps functionality.

## Structure

```
mock-project/
├── frontend/          # Next.js application
│   ├── package.json
│   ├── next.config.js
│   ├── pages/
│   │   └── index.tsx
│   └── .env.example
├── backend/           # FastAPI application
│   ├── pyproject.toml
│   ├── main.py
│   └── .env.example
└── README.md
```

## Usage

### Test Project Analysis

```bash
cd docs/mock-project
openops chat .

# In the chat:
# > Analyze this project
```

### Test Deployment (Dry Run)

```bash
openops deploy --dry-run
```

### Test with Specific Platform

```bash
# Frontend to Vercel
openops deploy frontend/ --platform vercel --dry-run

# Backend to Railway
openops deploy backend/ --platform railway --dry-run
```

## Expected Analysis Output

When analyzing this project, OpenOps should detect:

1. **Project Type**: Monorepo with 2 services
2. **Frontend Service**:
   - Framework: Next.js 14
   - Language: TypeScript
   - Type: Frontend
   - Required env: `NEXT_PUBLIC_API_URL`
   
3. **Backend Service**:
   - Framework: FastAPI
   - Language: Python
   - Type: Backend
   - Required env: `DATABASE_URL`, `JWT_SECRET`

## Keypoints (Expected)

- Monorepo with frontend and backend services
- Frontend depends on backend API
- Backend requires PostgreSQL database
- No deployment configuration exists
- Missing: vercel.json, railway.toml
