# Step 1: Use an official Python runtime as a base image
# Here we use the slim version of Python 3.9 to keep the image lightweight
FROM python:3.9-slim
# Step 2: Set the working directory in the container
# This ensures that all subsequent commands are run inside the /app directory
WORKDIR /app
# Step 3: Copy the requirements file into the container
# This allows Docker to install dependencies before copying the rest of the application,
# making use of Docker's layer caching to speed up builds when dependencies don't change
COPY requirements.txt requirements.txt
# Step 4: Install the required Python packages
# Use pip to install the dependencies specified in requirements.txt
RUN pip install -r requirements.txt
# Step 5: Copy the rest of the application code into the container
# This step copies all the remaining files in the current directory to the /app directory in the container
COPY . .
# Step 6: Set the command to run the application
# The CMD instruction specifies what command to run within the container when it starts
CMD ["python", "app.py"]