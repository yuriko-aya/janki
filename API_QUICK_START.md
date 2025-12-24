# API Quick Start Guide

## For Team Admins

### 1. Get Your API Token

1. Go to the admin panel: `https://your-domain.com/admin/`
2. Log in with your credentials
3. Navigate to **Users** → Find your username → Click to edit
4. Scroll down to the **API Token** section
5. If no token exists, one will be created when you save
6. Copy the token key (it looks like: `9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b`)

**Important:** Treat this token like a password. Anyone with this token can submit scores on your behalf.

### 2. Test the API

Using cURL (replace `YOUR_TOKEN` and `YOUR_TEAM_SLUG`):

```bash
# Get member IDs first by viewing your team members page
# Then submit a session:

curl -X POST https://your-domain.com/api/teams/YOUR_TEAM_SLUG/sessions/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "2024-12-23-game1",
    "session_date": "2024-12-23",
    "scores": [
      {"member_name": "Alice", "score": 35000, "chombo": false},
      {"member_name": "Bob", "score": 30000, "chombo": false},
      {"member_name": "Charlie", "score": 25000, "chombo": false},
      {"member_name": "Diana", "score": 10000, "chombo": true}
    ]
  }'
```

### 3. Common Use Cases

**Submit a new session:**
```bash
POST /api/teams/{team_slug}/sessions/
```

**Update existing session:**
```bash
PUT /api/teams/{team_slug}/sessions/{session_id}/
```

**Delete a session:**
```bash
DELETE /api/teams/{team_slug}/sessions/{session_id}/delete/
```

## For Developers

### Python Example

```python
import requests

class MahjongAPIClient:
    def __init__(self, base_url, token, team_slug):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json"
        }
        self.team_slug = team_slug
    
    def submit_session(self, session_id, scores, session_date=None):
        """
        Submit a new session.
        
        Args:
            session_id: Unique identifier for the session
            scores: List of dicts with member_id, score, chombo
            session_date: Optional date string (YYYY-MM-DD)
        """
        payload = {
            "session_id": session_id,
            "scores": scores
        }
        if session_date:
            payload["session_date"] = session_date
        
        response = requests.post(
            f"{self.base_url}/teams/{self.team_slug}/sessions/",
            headers=self.headers,
            json=payload
        )
        return response.json()

# Usage
client = MahjongAPIClient(
    base_url="https://your-domain.com/api",
    token="your-token-here",
    team_slug="my-team"
)

result = client.submit_session(
    session_id="2024-12-23-evening",
    scores=[
        {"member_name": "Alice", "score": 35000, "chombo": False},
        {"member_name": "Bob", "score": 30000, "chombo": False},
        {"member_name": "Charlie", "score": 25000, "chombo": False},
        {"member_name": "Diana", "score": 10000, "chombo": True},
    ],
    session_date="2024-12-23"
)

print(result)
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const API_BASE_URL = 'https://your-domain.com/api';
const TOKEN = 'your-token-here';
const TEAM_SLUG = 'my-team';

async function submitSession(sessionId, scores, sessionDate = null) {
  const payload = {
    session_id: sessionId,
    scores: scores
  };
  
  if (sessionDate) {
    payload.session_date = sessionDate;
  }
  
  try {
    const response = await axios.post(
      `${API_BASE_URL}/teams/${TEAM_SLUG}/sessions/`,
      payload,
      {
        headers: {
          'Authorization': `Token ${TOKEN}`,
          'Content-Type': 'application/json'
        }
      }
    );
    return response.data;
  } catch (error) {
    console.error('Error:', error.response.data);
    throw error;
  }
}

// Usage
submitSession(
  '2024-12-23-evening',
  [
    { member_name: 'Alice', score: 35000, chombo: false },
    { member_name: 'Bob', score: 30000, chombo: false },
    { member_name: 'Charlie', score: 25000, chombo: false },
    { member_name: 'Diana', score: 10000, chombo: true }
  ],
  '2024-12-23'
).then(result => console.log(result));
```

## Security Best Practices

1. **Never commit tokens to version control**
2. **Store tokens in environment variables or secure vaults**
3. **Regenerate tokens if compromised** (delete in admin and save to create new)
4. **Use HTTPS only** for API requests
5. **Validate all member IDs** before submission

## Troubleshooting

**401 Unauthorized:**
- Token is missing or invalid
- Check the Authorization header format: `Token your-token-here`

**403 Forbidden:**
- You're not the admin of this team
- Verify you're using the correct team slug

**400 Bad Request:**
- Invalid data format
- Missing required fields
- Check the error response for details

**409 Conflict:**
- Session already exists
- Use PUT to update instead of POST

For full documentation, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
