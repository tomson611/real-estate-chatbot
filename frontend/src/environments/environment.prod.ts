declare const process: {
  env: {
    [key: string]: string | undefined;
  }
};

export const environment = {
  production: true,
  apiUrl: 'API_URL_PLACEHOLDER'  // This will be replaced during build
}; 