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
const testingDir = path.resolve('./testing/data');
async function waitForFileCount(dirPath: string, targetCount: number, timeout = 10000): Promise<void> {
  const start = Date.now();
  while (true) {
    var files = await readdir(dirPath)
    files = files.filter(file => file.endsWith('.json'));
    if (files.length == targetCount) return;
    if (Date.now() - start > timeout) {
      throw new Error(`Timeout: ${targetCount} files not found in ${dirPath} within ${timeout}ms`);
    }
    await new Promise((r) => setTimeout(r, 25));
  }
}

// clean directory
async function clearDir(dir: string) {
  const files = await readdir(dir);
  await fs.promises.mkdir(testingDir, { recursive: true });
  await Promise.all(files.map(file => rm(path.join(dir, file), { force: true, recursive: true })));
}

test.beforeAll(async () => {
  await clearDir(speechDir);
  await clearDir(transcriptDir);
});
test.describe.parallel('voice_test_parallel', () => {
    
    logins.forEach(([email, password], index) => {

        test(`voice_test_user_${index}`, async ({ page }, testInfo) => {

        page.on('console', msg => {
            console.log('[browser]', msg.text());
        });

        await page.addInitScript(() => {
            (window as any).__speechLog = [];
            const origSpeak = speechSynthesis.speak.bind(speechSynthesis);
            speechSynthesis.speak = (utt: SpeechSynthesisUtterance) => {
            const txt = utt.text;
            utt.addEventListener('start', () => {
                (window as any).__speechLog.push({event:'start', text:txt, time:Date.now()});
            });
            utt.addEventListener('end', () => {
                (window as any).__speechLog.push({event:'end', text:txt, time:Date.now()});
            });
            origSpeak(utt);
            };
        });

        await page.addInitScript(() => {
            (window as any).__audioLog = [];
            const audioElement = document.getElementById('audioElement');
            if (audioElement) {
            audioElement.addEventListener('play', () => {
                console.log('Audio play event triggered for audioElement');
                (window as any).__audioLog.push({ event: 'play', time: Date.now() });
            });
            audioElement.addEventListener('error', (e) => {
                console.error('Audio element error:', e);
            });
            } else {
            console.warn('audioElement not found during init');
            }
        });
        await page.goto('http://localhost:5173/auth');
        await page.getByRole('textbox', { name: 'email' }).fill(email!);
        await page.getByRole('textbox', { name: 'password' }).fill(password!);
        await page.getByRole('button', { name: 'Sign in' }).click();
        await page.getByRole('button', { name: 'New Chat' }).click();
        await page.getByRole('button', { name: 'Call' }).click();
        //listen to faux mic input
        await waitForFileCount(transcriptDir, 2, 45000);        

        if(API_TTS){
            await waitForFileCount(speechDir, 1, 30000);
            const first = Date.now();
            await waitForFileCount(speechDir, 2, 30000);
            const second = Date.now();

            if (second - first > 1000) {
            console.log('TTS not concurrent enough');
            return;  
            }
            console.log('Speech to text and TTS concurrent');
        }else {
            let log;
            try {
            await page.waitForFunction((n) => {
                    const log = (window as any).__speechLog;
                    return Array.isArray(log) && log.filter((e: any) => e.event === 'start').length >= n;
                    }, 1, { timeout: 30_000 });

                log = await page.evaluate(() => (window as any).__speechLog);
                console.log(`Speech log from browser (worker ${index}):`, log);
                } catch (err) {
                    console.error(`waitForFunction never resolved in worker ${index}:`, err);
                    log = await page.evaluate(() => (window as any).__speechLog ?? []);
                    console.log(`Partial speech log (worker ${index}):`, log);
                    throw err;
                }
                
                fs.writeFileSync(path.join(`${testingDir}`,`${index}-speech-timing.json`), JSON.stringify(log));
                await page.waitForTimeout(3000);
            }
        });
    });
});
test.describe.serial('voice_test_serial', () => {
    test.afterAll("compare timing", () => {
    const timings: any[] = [];
    for (let i = 0; i < logins.length; i++) {
        const timing = fs.readFileSync(`${testingDir}/${i}-speech-timing.json`, 'utf8');
        timings.push(JSON.parse(timing));
    }
    if(Math.abs(timings[0][0].time - timings[1][0].time) < 500){
        console.log('Speech to text and TTS concurrent');
    }else{
        console.log('Speech to text and TTS not concurrent');
    }
    });
});