import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormField, FormRoot, email, form, required, submit } from '@angular/forms/signals';
import { Auth } from '../../core/auth/auth';
import { AuthCredentials } from '../../core/auth/auth.models';
import { AuthShell } from '../auth-shell/auth-shell';
import { PasswordField } from '../password-field/password-field';

@Component({
  selector: 'sign-in',
  imports: [AuthShell, FormField, FormRoot, PasswordField, RouterLink],
  templateUrl: './sign-in.html',
  styleUrl: './sign-in.scss',
})
export class SignIn {
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);

  private readonly credentials = signal<AuthCredentials>({ email: '', password: '' });

  protected readonly credentialsForm = form(this.credentials, (path) => {
    required(path.email, { message: 'Email is required' });
    email(path.email, { message: 'Enter a valid email address' });
    required(path.password, { message: 'Password is required' });
  });

  protected readonly emailInvalid = computed(
    () => this.credentialsForm.email().touched() && this.credentialsForm.email().errors().length > 0,
  );

  protected async onSubmit() {
    await submit(this.credentialsForm, async (rootField) => {
      try {
        await this.auth.login(rootField().value());
        await this.router.navigateByUrl('/chat');
        return undefined;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Login failed';
        return [{ fieldTree: this.credentialsForm.password, kind: 'server', message }];
      }
    });
  }
}
