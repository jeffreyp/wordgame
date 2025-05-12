# WordGrid - Two Player Word Game

WordGrid is a real-time two player word game where players compete to find words in a 4x4 grid of letters. The game is playable over a network on both desktop and mobile devices.

Try it [here](https://wordgame-muddy-bird-2759.fly.dev)!

## How to Play

1. Create a new game or join an existing one with a room code
2. Each game features a randomly generated 4x4 grid of letters
3. Players have 120 seconds to find as many valid English words as possible
4. Words must be at least 3 letters long
5. Longer words are worth more points
6. Words found by both players are cancelled out
7. The player with the highest score at the end wins

## Features

- Real-time gameplay using WebSockets
- Responsive design for desktop and mobile
- Room-based system for easy game creation and joining
- English dictionary validation using NLTK
- Scoring system based on word length

## Technical Details

- Backend: Flask with Flask-SocketIO
- Frontend: HTML, CSS, JavaScript
- Communication: WebSockets for real-time updates
- Dictionary: NLTK English words corpus

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure settings
4. Run the application:
   ```
   python app.py
   ```

## Deployment

The application is ready for deployment to platforms like Heroku, which support Python and WebSockets. A Procfile is included for easy deployment.

## License

MIT
