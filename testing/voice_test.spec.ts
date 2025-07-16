import { test, expect } from '@playwright/test';
import dotenv from 'dotenv';
import fs from 'fs';
import { readdir, rm} from 'fs/promises';

import path from 'path';
dotenv.config();
//boolean describing whetehr the local browser is doing the TTS, 
//or if an API is called for it.
//on openwebui, this is set in admin panel/settings/audio. 

const API_TTS = false;
const logins = [
  [process.env.LOGIN_A, process.env.PASSWORD_A],
  [process.env.LOGIN_B, process.env.PASSWORD_B],
];

const speechDir = path.resolve('./backend/data/cache/audio/speech');
const transcriptDir = path.resolve('./backend/data/cache/audio/transcriptions');

async function waitForFileCount(dirPath: string, targetCount: number, timeout = 10000): Promise<void> {
  const start = Date.now();
  while (true) {
    const files = await readdir(dirPath);
    if (files.length >= targetCount) return;
    if (Date.now() - start > timeout) {
      throw new Error(`Timeout: ${targetCount} files not found in ${dirPath} within ${timeout}ms`);
    }
    await new Promise((r) => setTimeout(r, 50));
  }
}

// clean directory
async function clearDir(dir: string) {
  const files = await readdir(dir);
  await Promise.all(files.map(file => rm(path.join(dir, file), { force: true, recursive: true })));
}

test.describe.parallel('voice_test_parallel', () => {
    
    logins.forEach(([email, password], index) => {

        test(`voice_test_user_${index}`, async ({ page }, testInfo) => {

        await clearDir(speechDir);
        await clearDir(transcriptDir);
        // page.on('console', msg => {
        // console.log('[browser]', msg.text());
        // });
        await page.goto('http://localhost:5173/auth');
        await page.getByRole('textbox', { name: 'email' }).fill(email!);
        await page.getByRole('textbox', { name: 'password' }).fill(password!);
        await page.getByRole('button', { name: 'Sign in' }).click();
        await page.getByRole('button', { name: 'New Chat' }).click();
        await page.getByRole('button', { name: 'Call' }).click();
        //listen to faux mic input
        await page.waitForTimeout(6000);

        await waitForFileCount(transcriptDir, 1);
        var first = Date.now();
        await waitForFileCount(transcriptDir, 2);
        var second = Date.now();
        if (second - first > 1000) {
          console.log('Speech to text not concurrent enough');
          return;
        }
        if(API_TTS){
            await waitForFileCount(speechDir, 1, 30000);
            first = Date.now();
            await waitForFileCount(speechDir, 2, 30000);
            second = Date.now();

            if (second - first > 1000) {
            console.log('TTS not concurrent enough');
            return;  
            }
            console.log('Speech to text and TTS concurrent');
        }else {
            await page.waitForTimeout(10000);
            await page.evaluate(() => {
                (window as any).__speechLog = [];
                const originalSpeak = speechSynthesis.speak;

                speechSynthesis.speak = function(utterance: SpeechSynthesisUtterance) {
                    utterance.onstart = () => {
                        (window as any).__speechLog.push({ event: 'start', time: Date.now() });
                    };
                    utterance.onend = () => {
                        (window as any).__speechLog.push({ event: 'end', time: Date.now() });
                    };
                    return originalSpeak.call(this, utterance);
                };
            });

            await page.waitForFunction(() => {
                const log = (window as any).__speechLog;
                return Array.isArray(log) &&
                    log.filter(entry => entry.event === 'end').length >= 2;
            }, { timeout: 30_000, polling: 'mutation' });
            await page.waitForTimeout(10000);
        }
        });
    });
});