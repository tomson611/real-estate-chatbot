declare const process: {
  env: {
    [key: string]: string | undefined;
  }
};

export const environment = {
  production: true,
  apiUrl: process.env['API_URL'] || 'http://127.0.0.1:8000/api'
}; 