import json
import requests
import discord
import time
import re
from applogging import AppLogger


def refreshYoutubeToken(config):
    refresh_url = "https://oauth2.googleapis.com/token"
    refresh_payload = {
        "client_id": config["YoutubeClientId"],
        "client_secret": config["YoutubeClientSecret"],
        "grant_type": "refresh_token",
        "refresh_token": config["YoutubeRefreshToken"]
    }
    try:
        req = requests.post(refresh_url, refresh_payload)
    except requests.RequestException as e:
        AppLog.error(str(e))
        AppLog.error("We got an exception using the requests library. Is the internet offline? Damn you cablevision!")
        AppLog.error("Shutting the bot down due to a fatal error.")
        exit(0)
    else:
        print(req.status_code)
        if req.status_code != 200:
            AppLog.error("Couldn't authenticate with the Youtube API to refresh the token. HTTP status code was " + str(
                req.status_code))
            AppLog.error("Shutting the bot down due to a fatal error.")
            exit(0)
        resp = req.json()
        access_token = resp["access_token"]
        print(access_token)
        return access_token


def getChannelIds(config, access_token):
    subscriptions_url = 'https://www.googleapis.com/youtube/v3/subscriptions?part=snippet,' \
                        'contentDetails&mine=true&maxResults=50&key=' + \
                        config["YoutubeAPIKey"]
    subscriptions_api_auth = {'Authorization': "Bearer " + access_token}
    try:
        req1 = requests.get(subscriptions_url, headers=subscriptions_api_auth)
    except requests.RequestException as e:
        AppLog.error(str(e))
        AppLog.error("We got an exception using the requests library. Is the internet offline? Damn you cablevision!")
        AppLog.error("Shutting the bot down due to a fatal error.")
        exit(0)
    else:
        if req1.status_code != 200:
            AppLog.error("The subscriptions endpoint API call failed. HTTP Status code was " + str(req1.status_code))
            AppLog.error("Shutting the bot down due to a fatal error.")
            exit(0)
        resp1 = req1.json()
        all_responses = []
        all_responses.append(resp1)
        nextpage = resp1.get("nextPageToken")
        request_counter = 1
        while nextpage is not None:
            print("Total is greater than page total, we need to go deeper")
            subscriptiions_url_paged = subscriptions_url + "&pageToken=" + nextpage
            req2 = requests.get(subscriptiions_url_paged, headers=subscriptions_api_auth)
            resp2 = req2.json()
            request_counter = request_counter + 1
            all_responses.append(resp2)
            nextpage = resp2.get("nextPageToken")
        AppLog.info("Made " + str(request_counter) + " API calls to the Subscriptions endpoint")
        channel_ids = []
        # print(all_responses)
        for x in all_responses:
            for i in x["items"]:
                channelid = i["snippet"]["resourceId"]["channelId"]
                channel_ids.append(channelid)
        deduplicated_channel_ids = distinctList(channel_ids)
        AppLog.info(str(len(deduplicated_channel_ids)) + " channels found")
        # print(json.dumps(channel_ids))
        failsafe_channel_ids = theYoutubeAPIsucksASS(deduplicated_channel_ids)
        return failsafe_channel_ids


def getChannelUploads(config, channel_ids, access_token):
    channel_ids_chunked = splitList(channel_ids, 10)
    request_counter = 1
    all_responses = []
    for channel_ids_list in channel_ids_chunked:
        channel_ids_str = ','.join(channel_ids_list)
        api_auth = {'Authorization': "Bearer " + access_token}
        url = "https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails&" \
              "maxResults=50&key=" + config["YoutubeAPIKey"] + "&id=" + channel_ids_str
        try:
            req = requests.get(url, headers=api_auth)
        except requests.RequestException as e:
            AppLog.error(str(e))
            AppLog.error(
                "We got an exception using the requests library. Is the internet offline? Damn you cablevision!")
            AppLog.error("Shutting the bot down due to a fatal error.")
            exit(0)
        else:
            st = req.status_code
            if st != 200:
                AppLog.error("The channels API call failed. HTTP Status code was " + str(st))
                AppLog.error("Shutting the bot down due to a fatal error.")
                exit(0)
            resp = req.json()
            all_responses.append(resp)
            request_counter = request_counter + 1
    playlist_ids = []
    AppLog.info("Made " + str(request_counter) + " calls to the Channels API")
    for x in all_responses:
        for i in x["items"]:
            print(json.dumps(i))
            u = i["contentDetails"]["relatedPlaylists"]["uploads"]
            if u != "":
                playlist_ids.append(u)
            else:
                AppLog.warn("No uploads playlist for channel found. " + i["snippet"]["title"], None, None, i["id"],
                            i["snippet"]["title"])
    AppLog.info("Found " + str(len(playlist_ids)) + " uploads playlists")
    return playlist_ids


def getVideosList(uploads_playlists, access_token, eligible):
    url = "https://www.googleapis.com/youtube/v3/playlistItems?part=" \
          "contentDetails,id,snippet,status&filter=playlistId&maxResults=50&playlistId="
    api_auth = {'Authorization': "Bearer " + access_token}
    videos = []
    for p in uploads_playlists:
        playlisturl = url + p
        try:
            req = requests.get(playlisturl, headers=api_auth)
        except requests.RequestException as e:
            AppLog.error(str(e))
            AppLog.error(
                "We got an exception using the requests library. Is the internet offline? Damn you cablevision!")
            AppLog.error("Shutting the bot down due to a fatal error.")
            exit(0)
        else:
            resp = req.json()
            if req.status_code == 200:
                for i in resp["items"]:
                    video_title = i["snippet"]["title"]
                    video_from = i["snippet"]["channelTitle"]
                    video_id = i["contentDetails"]["videoId"]
                    d = {"channel": video_from, "title": video_title, "id": video_id,
                         "channel_id": i["snippet"]["channelId"]}
                    ignore = False
                    patterns = [r'(?i)giant bombcast',
                                r'(?i)giant beastcast',
                                r'(?i)wan show',
                                r'(?i)mega64 podcast',
                                r'(?i)we be drummin']
                    chid = i["snippet"]["channelId"]
                    for px in patterns:
                        if re.search(px, video_title):
                            AppLog.info(
                                "ignoring " + video_id + " | " + video_title + " | Reason: Regex exclusion list",
                                video_id, video_title, chid, video_from)
                            ignore = True
                    if i["snippet"]["channelId"] not in eligible:
                        print(
                            "ignoring " + video_id + " | " + chid + " | " + video_title + " | Reason: Channel not in prev subs txt file, new subscription?",
                            video_id, video_title, chid, video_from)
                        ignore = True
                    z = {"title": d["title"], "channel": d["channel"], "id": d["id"], "ignore": ignore,
                         "channel_id": d["channel_id"]}
                    videos.append(z)
            else:
                st = req.status_code
                AppLog.error("The playlists API call failed. HTTP Status code was " + str(st) +
                             " and the playlist_id was " + p)
                AppLog.warn("The bot continues out of spite.")
    return videos


def deduplicateVideosList(api_vids, local_vids):
    new_vids = []
    for i in api_vids:
        if i["id"] not in local_vids:
            new_vids.append(i)
    return new_vids


def updateLocalVideoList(video_list):
    # video_ids = []
    file = open("videolist.txt", "at+")
    for i in video_list:
        print(i["id"])
        file.write(i["id"] + '\n')
    file.close()


def getLocalVideolist():
    file = open("videolist.txt", "rt+")
    lines = file.readlines()
    file.close()
    lines2 = []
    for l in lines:
        lines2.append(l.rstrip())
    # print(lines2)
    return lines2


def updateLocalChannelsList(chlist):
    file = open("channels.txt", "at+")
    for c in chlist:
        file.write(c + "\n")
    file.close()


def getLocalChannelsList():
    file = open("channels.txt", "rt+")
    d = file.readlines()
    e = []
    file.close()
    for i in d:
        e.append(i.rstrip())
    print(e)
    return e


def isChannelNewSubscription(channel_id, existingsubs):
    if channel_id in existingsubs:
        rc = False
    else:
        rc = True
    return rc


def excludeNewSubscriptions(subs, prev_subs):
    x = []
    for s in subs:
        if s.rstrip() in prev_subs:
            x.append(s.rstrip())
    return x


def splitList(inputlist, size):
    list_actual_size = len(inputlist)
    size_counter = 0
    new_list = []
    while size_counter < list_actual_size:
        print("Lower Bound: " + str(size_counter) + "  | Upper Bound: " + str(size + size_counter))
        tmp = inputlist[size_counter:(size + size_counter)]
        # print(tmp)
        size_counter = size + size_counter
        # print(size_counter)
        new_list.append(tmp)
    # print(new_list)
    # exit(0)
    return new_list


def distinctList(input_list):
    unique_values = set(input_list)
    unique_list = list(unique_values)
    return unique_list


def determineNewChannels(current, prev):
    lst = []
    for i in current:
        if i not in prev:
            lst.append(i)
    return lst


def theYoutubeAPIsucksASS(channel_ids_api):
    channel_ids_textfile = getLocalChannelsList()
    AppLog.info("Checking channels.txt because the youtube api is a bit like a candle in the wind.... unreliable.")
    AppLog.info("channels.txt = " + str(len(channel_ids_textfile)))
    for c in channel_ids_textfile:
        if c not in channel_ids_api:
            AppLog.info("The following channel ID was not in the API result | " + c, channel_id=c)
    for c in channel_ids_api:
        if c not in channel_ids_textfile:
            channel_ids_textfile.append(c)
            AppLog.info("Found a new channel from the API that wasn't in channels.txt | " + c, channel_id=c)
    AppLog.info("channels.txt + anything new = " + str(len(channel_ids_textfile)))
    AppLog.info("channels api calls = " + str(len(channel_ids_api)))
    return channel_ids_textfile


# Entry Point for the Program below this line

f = open("config.json", "rt+")
config = json.load(f)
f.close()
AppLog = AppLogger()
AppLog.info("Bot initialized! Process instance starting.")
bot = discord.Client()


@bot.event
async def on_ready():
    channelid = config["ChannelIdTvTime"]  # TV TIME
    # channelid = config["ChannelIdDev"]  # Dev Discord
    ch = bot.get_channel(channelid)
    access_token = refreshYoutubeToken(config)  # authenticate
    subscription_channels = distinctList(getChannelIds(config, access_token))  # what channels am i subbed to
    prev_subscription_channels = getLocalChannelsList()  # what channels was i subbed to last time
    eligible_subscription_channels = excludeNewSubscriptions(subscription_channels, prev_subscription_channels)
    # I do not want to dump 50 videos into the text channel if it's a new subscription
    # so ignore ones that are new this run
    upload_playlist_ids = getChannelUploads(config, subscription_channels,
                                            access_token)  # get the uploaded videos playlists
    videolist = getVideosList(upload_playlist_ids, access_token,
                              eligible_subscription_channels)  # check those playlists for videos
    oldvideolist = getLocalVideolist()  # check what videos already existed
    newvideos = deduplicateVideosList(videolist, oldvideolist)  # figure out the delta
    print("--New Videos--")
    print(newvideos)
    updateLocalVideoList(newvideos)  # append to the video list file
    new_channels = determineNewChannels(subscription_channels, prev_subscription_channels)
    updateLocalChannelsList(new_channels)
    counter = 0
    for v in newvideos:
        if v["ignore"] is False:
            counter = counter + 1
            txt = "https://youtube.com/watch?v=" + v["id"]
            print(txt)
            AppLog.info("Queued up video id " + v["id"], v["id"], v["title"], v["channel_id"], v["channel"])
            await ch.send(txt)
            time.sleep(20)
    print("done")
    AppLog.info("Queued all new videos. Process instance ending.")
    AppLog.info("This instance pushed " + str(counter) + " videos to TV Time")
    AppLog.clean_logs()
    exit(0)


if __name__ == "__main__":
    bot.run(config["DiscordBotToken"])
