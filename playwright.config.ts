
import { defineConfig, devices } from '@playwright/test';
import path from 'path';
/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// import dotenv from 'dotenv';
// import path from 'path';
// dotenv.config({ path: path.resolve(__dirname, '.env') });

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './testing',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 2 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  //reporter: [['json', { outputFile: 'results.json' }]],
  timeout: 1000_000,
  use: {
    ignoreHTTPSErrors: true,
    headless: false,
    trace: 'on-first-retry',
    //save auth state
    permissions: ['microphone'],
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chrome',  
      use: { ...devices['Desktop Chrome'],
        permissions: ['microphone'],
        launchOptions:{
            args:[
                '--use-fake-device-for-media-stream',
                `--use-file-for-fake-audio-capture=${path.resolve('./hello.wav')}`,

            ]
        },
        channel: 'chrome',
      },
    },
    
    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],

  /* Run your local dev server before starting the tests */
//   webServer: {
//     command: 'sh full_stack.sh',
//     url: 'http://localhost:5173',
//     reuseExistingServer: !process.env.CI,
//   },
});
