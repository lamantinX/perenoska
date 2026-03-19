# Commands

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
Copy-Item .env.example .env
```

## Run app

```powershell
uvicorn app.main:app --reload
```

## Run tests

```powershell
python -m pytest
```

## Run local verification

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

## Check git state

```powershell
git status --short --branch
git remote -v
```

## Point origin to user fork

```powershell
git remote set-url origin https://github.com/lamantinX/perenoska
```
