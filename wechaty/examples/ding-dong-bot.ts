#!/usr/bin/env -S node --no-warnings --loader ts-node/esm
/**
 * Wechaty - Conversational RPA SDK for Chatbot Makers.
 *  - https://github.com/wechaty/wechaty
 */
// https://stackoverflow.com/a/42817956/1123955
// https://github.com/motdotla/dotenv/issues/89#issuecomment-587753552
import 'dotenv/config'
import {Contact, Message, ScanStatus, WechatyBuilder, log} from 'wechaty'
import qrcodeTerminal from 'qrcode-terminal'
import fs from 'fs';
import yaml from 'js-yaml';
import path from 'path';
import axios from 'axios';

function onScan (qrcode: string, status: ScanStatus) {
  if (status === ScanStatus.Waiting || status === ScanStatus.Timeout) {
    const qrcodeImageUrl = [
      'https://wechaty.js.org/qrcode/',
      encodeURIComponent(qrcode),
    ].join('')
    log.info('StarterBot', 'onScan: %s(%s) - %s', ScanStatus[status], status, qrcodeImageUrl)

    qrcodeTerminal.generate(qrcode, { small: false })  // show qrcode on console

  } else {
    log.info('StarterBot', 'onScan: %s(%s)', ScanStatus[status], status)
  }
}

function onLogin (user: Contact) {
  log.info('StarterBot', '%s login', user)
}

function onLogout (user: Contact) {
  log.info('StarterBot', '%s logout', user)
}

async function onMessage (msg: Message) {
  const messageTime = msg.date();

  // Check if the message is newer than the bot's startup time
  if (messageTime < botStartTime) {
    return
  } 
  
  const configPath = '../channels/im/config.yml';
  const config = yaml.load(fs.readFileSync(configPath, 'utf8'));
  const from_contact = msg.talker()
  const alias = await from_contact.alias()
  const msg_id = msg.id
  log.error('StarterBot', 'contact alias: %s', alias)
  var host: string = config["host"]
  if (host === "0.0.0.0") {
    host = "127.0.0.1"
  }
  const port = config["port"]

  const userConfigPath = '../core/user.yml';
  const userConfig = yaml.load(fs.readFileSync(userConfigPath, 'utf8'));
  const users = userConfig["users"]
  const found = users.find(user => user.im && user.im.some(im => im === `wechat:${alias}`))
  if (!found) {
    log.info('StarterBot', 'Donot reply to this user: %s', alias)
    return
  }

  const url = `http://${host}:${port}/on_wechat_message`;
  
  try {
    const response = await axios.post(url, {
      "im_name": "wechat",
      "sender": `wechat:${alias}`,
      "message": msg.text(),
      "msg_id": msg_id
    })
    if (response.data.length === 0) {
      return
    }
    const json_data = JSON.stringify(response.data)
    log.info('StarterBot', 'channel response: %s', json_data) 
    await msg.say(response.data.response)      
  } catch (error) {
    log.error('StarterBot', 'channel error: %s', error)
  }


/*
  if (msg.type() === Message.type.Attachment || msg.type() === Message.Type.Image) {
    msg.toFileBox().then(file => {
      const name = file.name;
      console.log('Save file to: ' + name);
      file.toFile(name, true); // Save file to local file system
    }).catch(err => {
      console.error('Failed to save file:', err);
    });
  }
*/

}

const botStartTime = new Date();
const bot = WechatyBuilder.build({
  name: 'ding-dong-bot',

  //puppet:'wechaty-puppet-padlocal',
  ////puppetOptions: {
   // token: 'puppet_padlocal_54b6816c0eb9469e84c0fc44184e0517',
  //}
  puppet: 'wechaty-puppet-wechat4u'
  //puppet: 'wechaty-puppet-whatsapp'
  /**
   * You can specific `puppet` and `puppetOptions` here with hard coding:
   *
  puppet: 'wechaty-puppet-wechat',
  puppetOptions: {
    uos: true,
  },
   */
  /**
   * How to set Wechaty Puppet Provider:
   *
   *  1. Specify a `puppet` option when instantiating Wechaty. (like `{ puppet: 'wechaty-puppet-whatsapp' }`, see below)
   *  1. Set the `WECHATY_PUPPET` environment variable to the puppet NPM module name. (like `wechaty-puppet-whatsapp`)
   *
   * You can use the following providers locally:
   *  - wechaty-puppet-wechat (web protocol, no token required)
   *  - wechaty-puppet-whatsapp (web protocol, no token required)
   *  - wechaty-puppet-padlocal (pad protocol, token required)
   *  - etc. see: <https://wechaty.js.org/docs/puppet-providers/>
   */
  // puppet: 'wechaty-puppet-whatsapp'

  /**
   * You can use wechaty puppet provider 'wechaty-puppet-service'
   *   which can connect to remote Wechaty Puppet Services
   *   for using more powerful protocol.
   * Learn more about services (and TOKEN) from https://wechaty.js.org/docs/puppet-services/
   */
  //puppet: 'wechaty-puppet-service',
  //puppetOptions: {
  //   token: 'puppet_workpro_9fad9d59bc4a41298dada2eb7a82a820',
  //},
})

bot.on('scan',    onScan)
bot.on('login',   onLogin)
bot.on('logout',  onLogout)
bot.on('message', onMessage)

bot.start()
  .then(() => log.info('StarterBot', 'Starter Bot Started.'))
  .catch(e => log.error('StarterBot', e))
