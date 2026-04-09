# Hugging Face Space Setup Guide

Quick guide to get your CodeReview environment running on Hugging Face Spaces.

## Quick Start

### 1. Create Space

```bash
# Visit https://huggingface.co/spaces
# Click "Create new Space"
# Name: codereview-env
# SDK: Docker
# Hardware: CPU Basic
```

### 2. Clone and Push

```bash
# Clone your new Space
git clone https://huggingface.co/spaces/YOUR_USERNAME/codereview-env
cd codereview-env

# Copy project files
cp -r /path/to/codereview-env/* .

# Push to HF
git add .
git commit -m "Initial commit"
git push
```

### 3. Verify

```bash
# Wait for build (2-5 minutes)
# Then test:
curl https://YOUR_USERNAME-codereview-env.hf.space/health
```

## Space Configuration

Your Space should have these files in the root:

```
README.md          # Must have YAML frontmatter
Dockerfile         # Docker configuration
requirements.txt   # Python dependencies
openenv.yaml       # OpenEnv specification
server.py          # Entry point
```

## README.md Frontmatter

The README.md must start with YAML frontmatter:

```yaml
---
title: CodeReview RL Environment
emoji: 🔍
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
license: mit
short_description: OpenEnv environment for AI-driven code review
---
```

This is already configured in the provided README.md.

## Environment Variables

To run inference on the Space, add these secrets:

1. Go to Space Settings → Variables and secrets
2. Add:
   - `API_BASE_URL`: https://router.huggingface.co/v1
   - `MODEL_NAME`: Qwen/Qwen2.5-72B-Instruct
   - `HF_TOKEN`: Your Hugging Face token

## Testing Your Space

### Health Check

```bash
curl https://YOUR_USERNAME-codereview-env.hf.space/health
```

Expected: `{"status":"healthy"}`

### Metadata

```bash
curl https://YOUR_USERNAME-codereview-env.hf.space/metadata
```

Expected: JSON with environment info

### Reset

```bash
curl -X POST "https://YOUR_USERNAME-codereview-env.hf.space/reset?task=easy"
```

Expected: JSON with observation

### Step

```bash
curl -X POST "https://YOUR_USERNAME-codereview-env.hf.space/step" \
  -H "Content-Type: application/json" \
  -d '{"action":"analyze_code","pr_id":1,"value":null}'
```

Expected: JSON with reward and observation

## OpenEnv Validation

Run the official validator:

```bash
openenv validate --url https://YOUR_USERNAME-codereview-env.hf.space
```

All checks must pass for hackathon submission.

## Common Issues

### Space Not Building

- Check Dockerfile syntax
- Verify requirements.txt has all dependencies
- Review build logs in Space

### API Not Responding

- Wait for build to complete (check logs)
- Verify Space is running (not sleeping)
- Check health endpoint first

### Validation Fails

- Ensure openenv.yaml is correct
- Verify all endpoints return proper schemas
- Test endpoints manually

## Space Settings

Recommended settings:

- **Visibility:** Public
- **Hardware:** CPU Basic (sufficient for evaluation)
- **Sleep time:** Default (Space sleeps after inactivity)
- **Persistent storage:** Not needed

## Updating Your Space

```bash
# Make changes locally
git add .
git commit -m "Update: description"
git push
```

Space will automatically rebuild.

## Monitoring

Check Space health:

1. Visit your Space URL
2. Click "Logs" tab
3. Monitor application logs
4. Check for errors

## Performance

For better performance:

- Upgrade to CPU Upgrade or GPU hardware
- Implement caching
- Optimize Docker image size

## Support

- Hugging Face Spaces docs: https://huggingface.co/docs/hub/spaces
- OpenEnv docs: https://openenv.dev
- GitHub issues: https://github.com/YOUR_USERNAME/codereview-env/issues
