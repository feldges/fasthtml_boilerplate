# FastHTML Boilerplate

This is a boilerplate for FastHTML. It contains a simple login system and a database.

## Set Up
This boilerplate requires a Google OAuth client ID and secret. Go on the Google Cloud Platform and create a new OAuth client ID and secret.
Follow instructions from https://docs.fastht.ml/explains/oauth.html.

You can use any other OAuth provider, but you will need to modify the code accordingly.

Create a .env file with the following variables that you get from the Google Cloud Platform:
- AUTH_CLIENT_ID
- AUTH_CLIENT_SECRET

In main.py, you can modify the application_name and application_description. It will appear in the login page.

In main.py you can modify the database schema but you should keep the user table. For all tables you create, remember to add the xtra step in the code.
The xtra step is critical as it is used to restrict the access to the data: each user can only access its own data.

In terms_of_service.md, you can modify the terms of service.

You can also overwrite the favicon.ico file with you own image.


## Installation
To install the dependencies, run the following command:
```bash
poetry install
```

## Run the application
To run the application, you need to activate the virtual environment and run the main.py file.
```bash
poetry shell
python main.py
```

Happy coding!
