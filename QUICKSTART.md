# Quick Start Guide

Get the CodeReview RL Environment running in 5 minutes.

## 1. Clone Repository

```bash
git clone https://github.com/HardikBhaskar2010/Code-Review-Environment.git
cd Code-Review-Environment
```

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Run Server

```bash
uvicorn server:app --host 0.0.0.0 --port 7860
```

## 4. Test (in another terminal)

```bash
# Health check
curl http://localhost:7860/health

# Reset environment
curl -X POST "http://localhost:7860/reset?task=easy"

# Take action
curl -X POST "http://localhost:7860/step" \
  -H "Content-Type: application/json" \
  -d '{"action":"analyze_code","pr_id":1,"value":null}'
```

## 5. Run Baseline Agent

```bash
# Set environment variables
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
export HF_TOKEN=your_huggingface_token

# Run inference
python inference.py
```

## 6. Validate

```bash
openenv validate --url http://localhost:7860
```

## 7. Docker (Optional)

```bash
# Build
docker build -t codereview-env .

# Run
docker run -p 7860:7860 codereview-env

# Test
curl http://localhost:7860/health
```

## Next Steps

- Read [README.md](README.md) for full documentation
- See [DEPLOYMENT.md](DEPLOYMENT.md) for Hugging Face deployment
- Check [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for overview

## Troubleshooting

**Port already in use:**
```bash
# Use different port
uvicorn server:app --host 0.0.0.0 --port 8000
```

**Module not found:**
```bash
# Ensure you're in project root
pip install -r requirements.txt
```

**API key error:**
```bash
# Check environment variables
echo $HF_TOKEN
```

## Support

- GitHub Issues: https://github.com/HardikBhaskar2010/Code-Review-Environment/issues
- Documentation: See README.md
