# Agent Sandbox

This directory contains the agent sandbox implementation - a Docker-based virtual environment that agents use as their own computer to execute tasks, access the web, and manipulate files.

## Overview

The sandbox provides a complete containerized Linux environment with:
- Chrome browser for web interactions
- VNC server for accessing the Web User
- Web server for serving content (port 8080) -> loading html files from the /workspace directory
- Full file system access
- Full sudo access

## Customizing the Sandbox

You can modify the sandbox environment for development or to add new capabilities:

1. Edit files in the `docker/` directory
2. Build a custom image:
   ```
   cd backend/sandbox/docker
   docker compose build
   docker push kortix/suna:0.1.3
   ```
3. Test your changes locally using docker-compose

## Using a Custom Image

To use your custom sandbox image:

1. Change the `image` parameter in `docker-compose.yml` (that defines the image name `kortix/suna:___`)
2. Update the same image name in `backend/sandbox/sandbox.py` in the `create_sandbox` function
3. If using Daytona for deployment, update the image reference there as well

## Publishing New Versions

When publishing a new version of the sandbox:

1. Update the version number in `docker-compose.yml` (e.g., from `0.1.2` to `0.1.3`)
2. Build the new image: `docker compose build`
3. Push the new version: `docker push kortix/suna:0.1.3`
4. Update all references to the image version in:
   - `backend/utils/config.py`
   - Daytona images
   - Any other services using this image