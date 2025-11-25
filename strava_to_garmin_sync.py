#!/usr/bin/env python3
"""
Strava to Garmin Sync
Syncs activities from Strava to Garmin Connect
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta
from garth.exc import GarthHTTPError
from garminconnect import Garmin

# Configuration from environment variables
STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
STRAVA_REFRESH_TOKEN = os.getenv('STRAVA_REFRESH_TOKEN')
GARMIN_EMAIL = os.getenv('GARMIN_EMAIL')
GARMIN_PASSWORD = os.getenv('GARMIN_PASSWORD')
DAYS_TO_SYNC = int(os.getenv('DAYS_TO_SYNC', '7'))  # Default to last 7 days

def get_strava_access_token():
    """Get a fresh Strava access token using the refresh token"""
    print("🔑 Refreshing Strava access token...")

    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': STRAVA_CLIENT_ID,
            'client_secret': STRAVA_CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': STRAVA_REFRESH_TOKEN
        }
    )

    if response.status_code != 200:
        print(f"❌ Failed to refresh Strava token: {response.text}")
        sys.exit(1)

    data = response.json()
    print("✅ Strava token refreshed successfully")
    return data['access_token']

def get_strava_activities(access_token, days=7):
    """Fetch recent activities from Strava"""
    print(f"📥 Fetching Strava activities from last {days} days...")

    after_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())

    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(
        'https://www.strava.com/api/v3/athlete/activities',
        headers=headers,
        params={'after': after_timestamp, 'per_page': 50}
    )

    if response.status_code != 200:
        print(f"❌ Failed to fetch activities: {response.text}")
        sys.exit(1)

    activities = response.json()
    print(f"✅ Found {len(activities)} activities")
    return activities

def download_activity_gpx(access_token, activity_id):
    """Download activity as GPX from Strava"""
    headers = {'Authorization': f'Bearer {access_token}'}

    # Try GPX first (most compatible)
    response = requests.get(
        f'https://www.strava.com/api/v3/activities/{activity_id}/streams',
        headers=headers,
        params={
            'keys': 'time,latlng,altitude,heartrate,cadence,watts,temp',
            'key_by_type': 'true'
        }
    )

    if response.status_code == 200:
        return response.json()

    return None

def create_garmin_client():
    """Initialize and login to Garmin Connect"""
    print("🔐 Logging into Garmin Connect...")

    try:
        garmin = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
        garmin.login()
        print("✅ Logged into Garmin Connect")
        return garmin
    except GarthHTTPError as e:
        print(f"❌ Failed to login to Garmin: {e}")
        sys.exit(1)

def activity_exists_in_garmin(garmin, activity_name, activity_date):
    """Check if activity already exists in Garmin"""
    try:
        # Get activities from Garmin for that day
        activities = garmin.get_activities_by_date(
            activity_date.strftime('%Y-%m-%d'),
            activity_date.strftime('%Y-%m-%d')
        )

        # Check if any activity matches the name
        for act in activities:
            if act.get('activityName') == activity_name:
                return True
        return False
    except:
        # If we can't check, assume it doesn't exist
        return False

def convert_strava_to_tcx(activity, streams):
    """Convert Strava activity data to TCX format with enhanced metrics"""
    if not streams or 'time' not in streams:
        return None

    # Build basic TCX structure
    start_time = datetime.strptime(activity['start_date'], '%Y-%m-%dT%H:%M:%SZ')

    # Extract stream data
    time_data = streams.get('time', {}).get('data', [])
    latlng_data = streams.get('latlng', {}).get('data', [])
    altitude_data = streams.get('altitude', {}).get('data', [])
    heartrate_data = streams.get('heartrate', {}).get('data', [])
    cadence_data = streams.get('cadence', {}).get('data', [])
    watts_data = streams.get('watts', {}).get('data', [])
    temp_data = streams.get('temp', {}).get('data', [])

    # Calculate lap statistics
    avg_hr = activity.get('average_heartrate', 0)
    max_hr = activity.get('max_heartrate', 0)
    avg_watts = activity.get('average_watts', 0)
    max_watts = activity.get('max_watts', 0)
    avg_cadence = activity.get('average_cadence', 0)
    weighted_avg_watts = activity.get('weighted_average_watts', 0)

    # Build activity name with more context
    activity_notes = f"{activity['name']}"
    if activity.get('description'):
        activity_notes += f" - {activity['description']}"
    if activity.get('gear_id'):
        activity_notes += f" | Gear: {activity.get('gear_id')}"

    tcx = f"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
                        xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
  <Activities>
    <Activity Sport="{get_sport_type(activity['type'])}">
      <Id>{activity['start_date']}</Id>
      <Notes>{activity_notes}</Notes>
      <Lap StartTime="{activity['start_date']}">
        <TotalTimeSeconds>{activity['elapsed_time']}</TotalTimeSeconds>
        <DistanceMeters>{activity['distance']}</DistanceMeters>
        <MaximumSpeed>{activity.get('max_speed', 0)}</MaximumSpeed>
        <Calories>{activity.get('calories', 0)}</Calories>"""

    # Add heart rate stats if available
    if avg_hr:
        tcx += f"""
        <AverageHeartRateBpm><Value>{int(avg_hr)}</Value></AverageHeartRateBpm>
        <MaximumHeartRateBpm><Value>{int(max_hr)}</Value></MaximumHeartRateBpm>"""

    tcx += """
        <Intensity>Active</Intensity>
        <TriggerMethod>Manual</TriggerMethod>"""

    # Add extension data for power and cadence
    if avg_watts or avg_cadence:
        tcx += """
        <Extensions>
          <ns3:LX>"""
        if avg_watts:
            tcx += f"""
            <ns3:AvgWatts>{int(avg_watts)}</ns3:AvgWatts>
            <ns3:MaxWatts>{int(max_watts)}</ns3:MaxWatts>"""
        if avg_cadence:
            tcx += f"""
            <ns3:AvgRunCadence>{int(avg_cadence)}</ns3:AvgRunCadence>"""
        tcx += """
          </ns3:LX>
        </Extensions>"""

    tcx += """
        <Track>
"""

    # Add trackpoints with enhanced data
    for i, t in enumerate(time_data):
        point_time = start_time + timedelta(seconds=t)
        tcx += f"          <Trackpoint>\n"
        tcx += f"            <Time>{point_time.strftime('%Y-%m-%dT%H:%M:%SZ')}</Time>\n"

        if i < len(latlng_data):
            lat, lng = latlng_data[i]
            tcx += f"            <Position>\n"
            tcx += f"              <LatitudeDegrees>{lat}</LatitudeDegrees>\n"
            tcx += f"              <LongitudeDegrees>{lng}</LongitudeDegrees>\n"
            tcx += f"            </Position>\n"

        if i < len(altitude_data):
            tcx += f"            <AltitudeMeters>{altitude_data[i]}</AltitudeMeters>\n"

        if i < len(heartrate_data):
            tcx += f"            <HeartRateBpm><Value>{int(heartrate_data[i])}</Value></HeartRateBpm>\n"

        # Add cadence if available
        if i < len(cadence_data):
            tcx += f"            <Cadence>{int(cadence_data[i])}</Cadence>\n"

        # Add extensions for power and temperature
        has_extensions = (i < len(watts_data)) or (i < len(temp_data))
        if has_extensions:
            tcx += "            <Extensions>\n"
            tcx += "              <ns3:TPX>\n"

            if i < len(watts_data):
                tcx += f"                <ns3:Watts>{int(watts_data[i])}</ns3:Watts>\n"

            if i < len(temp_data):
                tcx += f"                <ns3:AirTemperature>{int(temp_data[i])}</ns3:AirTemperature>\n"

            tcx += "              </ns3:TPX>\n"
            tcx += "            </Extensions>\n"

        tcx += f"          </Trackpoint>\n"

    tcx += """        </Track>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>"""

    return tcx

def get_sport_type(strava_type):
    """Map Strava activity type to Garmin sport type"""
    mapping = {
        'Ride': 'Biking',
        'Run': 'Running',
        'Swim': 'Swimming',
        'Walk': 'Walking',
        'Hike': 'Hiking',
        'VirtualRide': 'Biking',
        'Workout': 'Other',
    }
    return mapping.get(strava_type, 'Other')

def upload_to_garmin(garmin, activity_name, tcx_data):
    """Upload activity to Garmin Connect"""
    try:
        # Save TCX to temporary file
        temp_file = f'/tmp/strava_activity_{int(time.time())}.tcx'
        with open(temp_file, 'w') as f:
            f.write(tcx_data)

        # Upload to Garmin
        result = garmin.upload_activity(temp_file)

        # Clean up
        os.remove(temp_file)

        return result
    except Exception as e:
        print(f"⚠️  Failed to upload {activity_name}: {e}")
        return None

def main():
    """Main sync process"""
    print("=" * 50)
    print("🔄 Strava to Garmin Sync Starting...")
    print("=" * 50)

    # Validate environment variables
    if not all([STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN, GARMIN_EMAIL, GARMIN_PASSWORD]):
        print("❌ Missing required environment variables!")
        print("Required: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN, GARMIN_EMAIL, GARMIN_PASSWORD")
        sys.exit(1)

    # Get Strava access token
    access_token = get_strava_access_token()

    # Fetch Strava activities
    activities = get_strava_activities(access_token, DAYS_TO_SYNC)

    if not activities:
        print("✅ No activities to sync")
        return

    # Login to Garmin
    garmin = create_garmin_client()

    # Process each activity
    uploaded_count = 0
    skipped_count = 0

    for activity in activities:
        activity_name = activity['name']
        activity_type = activity['type']
        activity_date = datetime.strptime(activity['start_date'], '%Y-%m-%dT%H:%M:%SZ')

        print(f"\n📍 Processing: {activity_name} ({activity_type}) - {activity_date.strftime('%Y-%m-%d %H:%M')}")

        # Check if already in Garmin
        if activity_exists_in_garmin(garmin, activity_name, activity_date):
            print(f"   ⏭️  Already in Garmin, skipping")
            skipped_count += 1
            continue

        # Download activity data
        streams = download_activity_gpx(access_token, activity['id'])

        if not streams:
            print(f"   ⚠️  No stream data available, skipping")
            skipped_count += 1
            continue

        # Convert to TCX
        tcx_data = convert_strava_to_tcx(activity, streams)

        if not tcx_data:
            print(f"   ⚠️  Failed to convert to TCX, skipping")
            skipped_count += 1
            continue

        # Upload to Garmin
        result = upload_to_garmin(garmin, activity_name, tcx_data)

        if result:
            print(f"   ✅ Uploaded successfully")
            uploaded_count += 1
        else:
            skipped_count += 1

        # Be nice to the APIs
        time.sleep(2)

    print("\n" + "=" * 50)
    print(f"✅ Sync Complete!")
    print(f"   📤 Uploaded: {uploaded_count}")
    print(f"   ⏭️  Skipped: {skipped_count}")
    print("=" * 50)

if __name__ == '__main__':
    main()
