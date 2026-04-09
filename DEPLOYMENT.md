# Deployment Guide

This guide covers deploying the CodeReview RL Environment to Hugging Face Spaces.

## Prerequisites

- Hugging Face account
- Git installed locally
- Docker installed (for local testing)

## Step 1: Create Hugging Face Space

1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Configure:
   - **Name:** `codereview-env` (or your preferred name)
   - **License:** MIT
   - **SDK:** Docker
   - **Hardware:** CPU Basic (free tier works)
4. Click "Create Space"

## Step 2: Clone Your Space Repository

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/codereview-env
cd codereview-env
```

## Step 3: Copy Project Files

Copy all files from this project to your Space repository:

```bash
# From the codereview-env project directory
cp -r * /path/to/your/space/codereview-env/
```

## Step 4: Configure Environment Variables (Optional)

If you want to test inference on the Space, add these secrets in Space settings:

- `API_BASE_URL`: Your LLM API endpoint
- `MODEL_NAME`: Model identifier
- `HF_TOKEN`: Your Hugging Face token

## Step 5: Push to Hugging Face

```bash
git add .
git commit -m "Initial deployment of CodeReview RL Environment"
git push
```

## Step 6: Wait for Build

Hugging Face will automatically:
1. Build the Docker image
2. Start the container
3. Expose the API on port 7860

Monitor build logs in the Space's "Logs" tab.

## Step 7: Verify Deployment

Once deployed, test the endpoints:

```bash
# Health check
curl https://YOUR_USERNAME-codereview-env.hf.space/health

# Metadata
curl https://YOUR_USERNAME-codereview-env.hf.space/metadata

# Reset environment
curl -X POST "https://YOUR_USERNAME-codereview-env.hf.space/reset?task=easy"
```

## Step 8: Run OpenEnv Validator

```bash
openenv validate --url https://YOUR_USERNAME-codereview-env.hf.space
```

Expected output:
```
✓ Environment responds
✓ Reset endpoint works
✓ Step endpoint works
✓ Schema is valid
✓ All tasks available
passed: true
```

## Troubleshooting

### Build Fails

- Check Dockerfile syntax
- Verify all dependencies in requirements.txt
- Check build logs for specific errors

### Container Crashes

- Check application logs in Space
- Verify port 7860 is exposed
- Test locally with Docker first

### API Not Responding

- Verify Space is running (not sleeping)
- Check health endpoint
- Review application logs

### Validation Fails

- Ensure all endpoints return correct schemas
- Verify openenv.yaml is correct
- Test endpoints manually with curl

## Local Docker Testing

Before deploying, test locally:

```bash
# Build
docker build -t codereview-env .

# Run
docker run -p 7860:7860 codereview-env

# Test
curl http://localhost:7860/health
```

## Updating Deployment

To update your Space:

```bash
git add .
git commit -m "Update: description of changes"
git push
```

Hugging Face will automatically rebuild and redeploy.

## Performance Optimization

For production use:

1. **Upgrade Hardware:** Consider CPU Upgrade or GPU for faster inference
2. **Add Caching:** Implement response caching for repeated queries
3. **Rate Limiting:** Add rate limiting to prevent abuse
4. **Monitoring:** Set up logging and monitoring

## Security Considerations

1. **API Keys:** Never commit API keys to git
2. **Environment Variables:** Use Space secrets for sensitive data
3. **Input Validation:** Validate all user inputs
4. **Rate Limiting:** Implement rate limiting

## Support

For issues:
- Check Hugging Face Spaces documentation
- Review OpenEnv specification
- Open issue on GitHub repository
