#base image
FROM python:3.12-slim

#work directory
WORKDIR /app

#REQUIREMENTS
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

#COPY project
COPY . .

#This is for creating the local storage
RUN mkdir -p /app/upload

#fastapi port
EXPOSE 8000

#Run the app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]