import json
import boto
import urllib
from boto.dynamodb2.fields import HashKey, RangeKey, KeysOnlyIndex, GlobalAllIndex
from boto.dynamodb2.table import Table, Item
from boto.dynamodb2.types import NUMBER
from boto.dynamodb2.exceptions import ItemNotFound
from time import sleep
from datetime import timedelta, datetime

what_message = '''
  voting system for user posts.

  voting rules:
  * first upvote is 1 points, rest is 2
  * first downvote does not count, rest is -1
  * if you get full house(upvote from all members) you get member_count*10 points
  * if you get all out(downvote from all members) you lose member_count*10/2 points
  * sequential upvotes(upvotes until first downvote) receives multiplier
  * upvotes within an hour after post gets +member_count points

  at the end of each week, member with highest points wins, and gets to have a chance to add someone to the group, or have one coffee(type-place is his choice) from the rest of group members.

  when you reached 5 wins in total, you can also choose to remove someone from group as well. Wins resets after this.
'''
#---
how_message = '''

  * you can vote a post by replying it with thumbs up or thumbs down.
  * stickers works too
  * only first vote will count for every member
  * you cannot vote yourself
  * you cannot remove/edit your vote
  * you can only vote spotify and youtube links
  * ethics are nice, have them
'''
#---
with_message = '''
  * python
  * dynamodb
  * boto
  * love
'''
#---
where_message = '''
  https://github.com/kubudi/telegram_voter_boter
'''
#---
who_message = '''
  https://github.com/kubudi
'''
#---
other_message = '''
  I don't speak peasant. Be brief
'''
#---
help_message = '''
you ca ask me these questions:
* /what
* /why
* /how
* /with
* /where
* /who
'''
#---
#constant for now
related_chat = '-1001124075229'
api_key = '348516303:AAHquhUlBr4OdA-EfpBSado5A848AgpMtuE'
base_url = 'https://api.telegram.org/bot'

#Commands
help  = '/help'
what  = '/what'
why   = '/why'
how   = '/how'
_with = '/with'
where = '/where'
who   = '/who'
stats = '/stats'

#spam preventer
default = datetime.now()
last_run_time = {
  help: default,
  what: default,
  why: default,
  how: default,
  _with: default,
  where: default,
  who: default,
  stats: default,
  'other': default
}

thirty_seconds = timedelta(seconds=20)

#-----
def get_table():
  conn = boto.dynamodb2.connect_to_region('eu-central-1', aws_access_key_id='AKIAIKDDC3ABD5JKQ6XQ', aws_secret_access_key='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')
  table = Table('test_bot', connection=conn)
  return table

table = get_table()

def get_updates():
  json_res = urllib.urlopen('{}{}/getUpdates'.format(base_url, api_key)).read()
  res = json.loads(json_res)
  updates = res['result']

  print('Received {} new messages'.format(len(updates) - 1))
  return updates

def remove_processed(last_read):
  # print('Removing processed updates')
  urllib.urlopen('{}{}/getUpdates?offset={}'.format(base_url, api_key, last_read)).read()

def get_member_count(chat_id):
  member_count_json = urllib.urlopen('{}{}/getChatMembersCount?chat_id={}'.format(base_url, api_key, chat_id)).read()
  member_count = json.loads(member_count_json)['result']

  # print('Member count is {}'.format(member_count))
  return member_count

def get_share(share_to_score, user_to_score):
  try:
    share = table.get_item(share_id = share_to_score)
    print('Fetched share from db. Share id is: {}'.format(share_to_score))
  except ItemNotFound:
    share = Item(table, data={
     'share_id': share_to_score,
     'username': user_to_score,
     'points': 0,
     'voters': [],
     'upvote_count': 0,
     'downvote_count': 0,
     'last_vote': '',
     'first_upvote': True,
     'first_downvote': True
    })
    print('Created new share object. Share id is: {}'.format(share_to_score))

  return share

def get_vote(message):
  #unicode thumbs
  thumbs_up = u'\ud83d\udc4d' 
  thumbs_down = u'\ud83d\udc4e'

  if('text' in message):
    if(thumbs_up in message['text']):
      vote = 'upvote'
    elif(thumbs_down in message['text']):
      vote = 'downvote'

  if('sticker' in message):
    if(thumbs_up == message['sticker']['emoji']):
      vote = 'upvote'
    elif(thumbs_down == message['sticker']['emoji']):
      vote = 'downvote'

  print('Vote calculated: {}'.format(vote))
  return vote

def calculate_point(vote, message, share):
  member_count = get_member_count(str(message['chat']['id']))

  sequential = share['last_vote'] == 'upvote'
  within_hour = (message['date'] - message['reply_to_message']['date']) < 3600
  first_upvote = share['first_upvote']
  first_downvote = share['first_downvote']
  full_house = share['upvote_count'] == (member_count - 3)
  all_out = share['downvote_count'] == (member_count - 3)

  #calculate_point
  if(vote == 'upvote'):
    point = 1
    if not first_upvote: point += 1
    if within_hour: point += member_count
    if sequential: point = point * share['upvote_count']
    if full_house: point = member_count * 10
  elif(vote == 'downvote'):
    point = 0
    if not first_downvote: point += -1
    if all_out: point = (member_count * -10) / 2


  print('Point calculated: {}'.format(point))
  return point

def update_share(share, vote, point, user_who_score):
  share['last_vote'] = vote
  if(vote == 'upvote'): 
    share['first_upvote'] = False
    share['upvote_count'] += 1
  elif(vote == 'downvote'): 
    share['first_downvote'] = False
    share['downvote_count'] += 1
  share['voters'].append(user_who_score)
  share['points'] = share['points'] + point

  print(share['voters'])
  share.save()
  print('Share saved')

def is_song(message):
  reply = message['reply_to_message']
  if('text' in reply):
    text = reply['text']
    return ('www.youtube.com' in text) or ('youtu.be' in text) or ('spotify:track' in text) or ('open.spotify.com' in text)
  else:
    return False

def process_vote(message):
  print('Vote found, processing...')
  user_who_score = str(message['from']['username'])
  user_to_score  = str(message['reply_to_message']['from']['username'])
  share_to_score = str(message['reply_to_message']['message_id'])

  print('share owner: {}'.format(user_to_score))
  print('voter: {}'.format(user_who_score))

  #is it a song
  if (not is_song(message)):
    return 'This is not a song'

  #can't vote to yourself
  if(user_who_score == user_to_score):
    return 'Cannot vote to self'

  share = get_share(share_to_score, user_to_score)

  #has already voted?
  if(user_who_score in share['voters']):
    return 'User has already voted'

  vote = get_vote(message)
  point = calculate_point(vote, message, share)

  update_share(share, vote, point, user_who_score)
  return 'Processing vote finished'

def command_help(chat_id):
  urllib.urlopen('{}{}/sendMessage?chat_id={}&text={}'.format(base_url, api_key, chat_id, help_message)).read()

def command_what(chat_id):
  urllib.urlopen('{}{}/sendMessage?chat_id={}&text={}'.format(base_url, api_key, chat_id, what_message)).read()

def command_why(chat_id):
  urllib.urlopen('{}{}/sendDocument?chat_id={}&document=https://media.giphy.com/media/FxEwsOF1D79za/giphy.gif'.format(base_url, api_key, chat_id)).read()

def command_how(chat_id):
  urllib.urlopen('{}{}/sendMessage?chat_id={}&text={}'.format(base_url, api_key, chat_id, how_message)).read()

def command_with(chat_id):
  urllib.urlopen('{}{}/sendMessage?chat_id={}&text={}'.format(base_url, api_key, chat_id, with_message)).read()

def command_where(chat_id):
  urllib.urlopen('{}{}/sendMessage?chat_id={}&text={}'.format(base_url, api_key, chat_id, where_message)).read()

def command_who(chat_id):
  urllib.urlopen('{}{}/sendMessage?chat_id={}&text={}'.format(base_url, api_key, chat_id, who_message)).read()

def command_other(chat_id):
  urllib.urlopen('{}{}/sendMessage?chat_id={}&text={}'.format(base_url, api_key, chat_id, other_message)).read()

def command_forbidden(chat_id):
  urllib.urlopen('{}{}/sendDocument?chat_id={}&document=https://s-media-cache-ak0.pinimg.com/originals/6a/c1/15/6ac1159890ca89ab59ff5f99761464af.gif'.format(base_url, api_key, chat_id)).read()

def command_stats(chat_id):
  shares = table.scan()
  stats = {}
  for share in shares:
    username = share['username']
    points = share['points']

    if(username in stats):
      stats[username] += points
    else:
      stats[username] = points

  stats_message = ""
  for key, value in stats.iteritems():
    stats_message += "@{}: {} \n".format(key, value)

  urllib.urlopen('{}{}/sendMessage?chat_id={}&text={}'.format(base_url, api_key, chat_id, stats_message)).read()

def process_command(message, chat_id):
  print('Command found, processing...')


  now = datetime.now()

  if(help in message['text']):
    if(now - last_run_time[help]> thirty_seconds):
      last_run_time[help]= now
      command_help(chat_id)
    else:
      return "Just ran the command, ignoring"
  elif(what in message['text']):
    if(now - last_run_time[what]> thirty_seconds):
      last_run_time[what]= now
      command_what(chat_id)
    else:
      return "Just ran the command, ignoring"
  elif(why in message['text']):
    if(now - last_run_time[why]> thirty_seconds):
      last_run_time[why]= now
      command_why(chat_id)
    else:
      return "Just ran the command, ignoring"
  elif(how in message['text']):
    if(now - last_run_time[how]> thirty_seconds):
      last_run_time[how]= now
      command_how(chat_id)
    else:
      return "Just ran the command, ignoring"
  elif(_with in message['text']):
    if(now - last_run_time[_with]> thirty_seconds):
      last_run_time[_with]= now
      command_with(chat_id)
    else:
      return "Just ran the command, ignoring"
  elif(where in message['text']):
    if(now - last_run_time[where]> thirty_seconds):
      last_run_time[where]= now
      command_where(chat_id)
    else:
      return "Just ran the command, ignoring"
  elif(who in message['text']):
    if(now - last_run_time[who]> thirty_seconds):
      last_run_time[who]= now
      command_who(chat_id)
    else:
      return "Just ran the command, ignoring"
  elif('yarr' in message['text']):
      command_forbidden(chat_id)
  elif(stats in message['text']):
    if(now - last_run_time[stats]> thirty_seconds):
      last_run_time[stats]= now
      command_stats(chat_id)
    else:
      return "Just ran the command, ignoring"
  else:
    if(now - last_run_time['other'] > thirty_seconds):
      last_run_time['other'] = now
      command_other(chat_id)
    else:
      return "Just ran the command, ignoring"

  return "Command executed"

def main():
  updates = get_updates()

  for update in updates[1:]:
    print('--------')
    if('message' not in update):
      print("Not a message, probably edit")
    else:
      message = update['message']
      chat_id = str(message['chat']['id'])
      #check if it's the correct channel
      if(chat_id != related_chat):
        print('Not this channel')
      else:
        #if it is a reply
        if('reply_to_message' in message):
          process_res = process_vote(message)
          print(process_res)
        elif('entities' in message and message['entities'][0]["type"] == 'bot_command'):
          process_res = process_command(message, chat_id)
          print(process_res)
        else:
          print('nothing to do')

  latest_id = str(updates[-1]['update_id'])
  # print('latest_id is: ' + latest_id)
  remove_processed(latest_id)
  sleep(1)
  main()
  return 'Success'


res = main()
print(res)