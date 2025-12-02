# Claude Professional Development Guidelines

## CRITICAL: Read this BEFORE proposing ANY solution

### Security - Rule #1: NEVER expose secrets

1. **NEVER ask for secrets** (API keys, passwords, tokens, client secrets)
2. **NEVER hardcode secrets** in any file that goes into git
3. **ALWAYS use environment variables** for secrets
4. **Understand what is secret vs public**:
   - ❌ SECRET: client_secret, API keys, passwords, tokens
   - ✅ PUBLIC: client_id, API endpoints, public configuration

### Before proposing a solution

1. **THINK** about security implications
2. **VERIFY** the solution doesn't expose secrets
3. **CHECK** if there are simpler alternatives
4. **TEST** mentally: "Would I do this in production?"

### Git and version control

1. **NEVER commit secrets** to git
2. If a secret was exposed in git history:
   - Revoke the credentials immediately
   - Create new credentials
   - Don't try to rewrite git history with secrets still in it

### Professional standards

1. **Client secrets belong ONLY in environment variables**
2. **Public values (like client_id) can be in code** - no need to over-complicate
3. **Always propose the simplest professional solution** first
4. **Don't over-engineer** - if something can be hardcoded safely, do it

### Environment variables on Render

For secrets, tell the user to:
1. Go to Render Dashboard → Service → Environment
2. Add the environment variable
3. **NEVER ask the user to tell you the secret value**

## Checklist before proposing a solution

- [ ] Does this solution expose any secrets? → FIX IT
- [ ] Am I asking the user for a secret? → DON'T
- [ ] Is this the simplest professional approach? → VERIFY
- [ ] Would this pass a security audit? → CHECK
- [ ] Am I over-complicating something simple? → SIMPLIFY

## Remember

**The user is a professional. Treat them like one. Don't make them clean up security messes.**
