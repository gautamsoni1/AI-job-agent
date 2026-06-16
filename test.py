import smtplib

email = "gautamsoni.hpp@gmail.com"
password = "tivpjjbqqoqwqvus"

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()

server.login(email, password)

print("Login Success")