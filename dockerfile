FROM python:3.14-slim

WORKDIR /app

# Install git and other dependencies
RUN apt-get update && apt-get install -y \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock streamlit_app.py /app/

# Install uv
RUN pip install uv

# Create virtual environment
RUN uv venv

# Install dependencies using uv
RUN uv pip install --requirement pyproject.toml

# Set environment variables with defaults (these can be overridden at runtime)
ENV OPENAI_API_KEY=""
ENV GITHUB_ACCESS_TOKEN=""
ENV GITHUB_REPO_NAME=""
ENV PORT=8501

# Expose the Streamlit port
EXPOSE ${PORT}

# Command to run the Streamlit app
CMD uv run streamlit run streamlit_app.py --server.port=${PORT} --server.address=0.0.0.0