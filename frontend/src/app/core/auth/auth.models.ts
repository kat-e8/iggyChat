export type AuthCredentials = {
  email: string;
  password: string;
};

export type SignUpCredentials = AuthCredentials & {
  confirmPassword: string;
};

export type AuthErrorBody = {
  detail?: string;
};
