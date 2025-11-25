# Strava to Garmin Sync Setup

This guide will help you set up automatic syncing from Strava to Garmin Connect.

## Why This Exists

The official Peloton-to-Garmin sync is currently broken due to Peloton API changes (see [Issue #795](https://github.com/philosowaffle/peloton-to-garmin/issues/795)). This workflow provides an alternative path: **Peloton → Strava → Garmin**.

## Prerequisites

- Peloton automatically syncing to Strava ✅
- Strava account
- Garmin Connect account
- GitHub repository with Actions enabled

## Setup Steps

### 1. Create a Strava API Application

1. Go to: https://www.strava.com/settings/api
2. Click **"Create an App"** (or use existing app)
3. Fill in the application details:
   - **Application Name**: "Strava to Garmin Sync"
   - **Category**: Choose any (e.g., "Data Importer")
   - **Club**: Leave blank
   - **Website**: Your GitHub repo URL (e.g., `https://github.com/yourusername/peloton-to-garmin`)
   - **Authorization Callback Domain**: `localhost`
4. Click **"Create"**
5. **Save these values** (you'll need them):
   - **Client ID** (shown immediately)
   - **Client Secret** (click "Show" to reveal)

### 2. Get Your Strava Refresh Token

You need to authorize your app and get a refresh token. Run these commands in Terminal:

#### Step A: Get Authorization Code

Replace `YOUR_CLIENT_ID` with your actual Client ID, then paste this URL into your browser:

```
https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all
```

Click **"Authorize"**. You'll be redirected to a URL like:
```
http://localhost/?state=&code=LONG_CODE_HERE&scope=read,activity:read_all
```

**Copy the `code=` value** (everything after `code=` and before `&scope`)

#### Step B: Exchange Code for Refresh Token

Replace the placeholders and run this `curl` command in Terminal:

```bash
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d code=YOUR_CODE_FROM_STEP_A \
  -d grant_type=authorization_code
```

The response will include a `refresh_token`. **Save this value!**

Example response:
```json
{
  "token_type": "Bearer",
  "expires_at": 1234567890,
  "expires_in": 21600,
  "refresh_token": "abc123def456...",  ← SAVE THIS
  "access_token": "xyz789..."
}
```

### 3. Add Secrets to GitHub

1. Go to your repository: `https://github.com/YOUR_USERNAME/peloton-to-garmin`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"** and add these three secrets:

| Secret Name | Value |
|-------------|-------|
| `STRAVA_CLIENT_ID` | Your Strava Client ID |
| `STRAVA_CLIENT_SECRET` | Your Strava Client Secret |
| `STRAVA_REFRESH_TOKEN` | Your refresh token from Step 2B |

**Note:** Your Garmin credentials (`P2G_GARMIN__EMAIL` and `P2G_GARMIN__PASSWORD`) should already be set up from the P2G workflow.

### 4. Test the Workflow

1. Go to: `https://github.com/YOUR_USERNAME/peloton-to-garmin/actions/workflows/sync_strava_to_garmin.yml`
2. Click **"Run workflow"**
3. Choose how many days to sync (default: 7 days)
4. Click **"Run workflow"**
5. Watch the logs to see it work!

## How It Works

- **Automatic Schedule**: Runs twice daily at midnight and noon CST
- **Manual Trigger**: Run anytime from GitHub Actions
- **Smart Sync**: Only uploads activities that don't already exist in Garmin
- **Default Range**: Syncs last 7 days of activities

## Workflow Details

The workflow:
1. Fetches your recent activities from Strava
2. Downloads the activity data (GPS, heart rate, etc.)
3. Converts to TCX format (compatible with Garmin)
4. Uploads to Garmin Connect
5. Skips activities already in Garmin (no duplicates)

## Troubleshooting

### "Failed to refresh Strava token"
- Check that your `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, and `STRAVA_REFRESH_TOKEN` are correct
- Make sure you completed Step 2 properly

### "Failed to login to Garmin"
- Verify your `P2G_GARMIN__EMAIL` and `P2G_GARMIN__PASSWORD` secrets are correct
- Make sure you don't have 2FA enabled on Garmin (not currently supported)

### "No activities to sync"
- Check that Peloton activities are showing up in Strava
- Try increasing the "days to sync" parameter

### Activities not appearing in Garmin
- Check the workflow logs for errors
- Verify the upload step completed successfully
- Sometimes Garmin takes a few minutes to process uploads

## Support

This is a custom workaround while the official P2G tool is broken. For issues:
- Check the workflow logs first
- Verify all secrets are set correctly
- Make sure Peloton → Strava sync is working

Once [Issue #795](https://github.com/philosowaffle/peloton-to-garmin/issues/795) is resolved, you can switch back to the official P2G workflow.
