import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormField, FormRoot, email, form, required, submit, validate } from '@angular/forms/signals';
import { Auth } from '../../core/auth/auth';
import { SignUpCredentials } from '../../core/auth/auth.models';
import { AuthShell } from '../auth-shell/auth-shell';
import { PasswordField } from '../password-field/password-field';

@Component({
  selector: 'sign-up',
  imports: [AuthShell, FormField, FormRoot, PasswordField, RouterLink],
  templateUrl: './sign-up.html',
  styleUrl: './sign-up.scss',
})
export class SignUp {
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);

  private readonly credentials = signal<SignUpCredentials>({
    email: '',
    password: '',
    confirmPassword: '',
  });

  protected readonly credentialsForm = form(this.credentials, (path) => {
    required(path.email, { message: 'Email is required' });
    email(path.email, { message: 'Enter a valid email address' });
    required(path.password, { message: 'Password is required' });
    required(path.confirmPassword, { message: 'Confirm your password' });
    validate(path.confirmPassword, ({ value, valueOf }) => {
      if (value() !== valueOf(path.password)) {
        return { kind: 'mismatch', message: 'Passwords do not match' };
      }
      return undefined;
    });
  });

  protected readonly emailInvalid = computed(
    () => this.credentialsForm.email().touched() && this.credentialsForm.email().errors().length > 0,
  );

  protected async onSubmit() {
    await submit(this.credentialsForm, async (rootField) => {
      const { email: signupEmail, password } = rootField().value();
      try {
        await this.auth.signup({ email: signupEmail, password });
        await this.router.navigateByUrl('/chat');
        return undefined;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Sign up failed';
        return [{ fieldTree: this.credentialsForm.email, kind: 'server', message }];
      }
    });
  }
}
