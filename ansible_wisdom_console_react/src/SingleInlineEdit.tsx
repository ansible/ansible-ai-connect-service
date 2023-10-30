import {EyeIcon, EyeSlashIcon, TimesIcon} from "@patternfly/react-icons";
import {Button, InputGroup, TextInput} from "@patternfly/react-core";
import {useTranslation} from "react-i18next";
import {useState} from "react";

export interface InlineTextInputProps {
    readonly value: string;
    readonly onChange: (value: string) => void;
    readonly 'aria-label': string;
    readonly placeholder: string;
    readonly isDisabled: boolean;
    readonly isPassword: boolean;
}

export const SingleInlineEdit = (props: InlineTextInputProps) => {
    const {t} = useTranslation();

    const {value, onChange, placeholder, isDisabled, isPassword} = props;
    const [passwordHidden, setPasswordHidden] = useState<boolean>(isPassword)

    return (
        <>
            {isPassword && (
                <InputGroup>
                    <TextInput
                        type={isPassword && passwordHidden ? "password" : "text"}
                        onChange={(value, event) => props.onChange?.(value)}
                        aria-label={props["aria-label"]}
                        placeholder={placeholder}
                        isDisabled={isDisabled}
                        data-testid={"model-settings-editor__input"}
                    />
                    <Button
                        variant="control"
                        onClick={() => setPasswordHidden(!passwordHidden)}
                        aria-label={passwordHidden ? t('ShowText') : t('HideText')}
                        data-testid={"model-settings-editor__toggleView"}>
                        {passwordHidden ? <EyeIcon/> : <EyeSlashIcon/>}
                    </Button>
                    <Button variant="plain"
                            aria-label={t('ClearText')}
                            title={t('ClearText')}
                            onClick={() => {
                                onChange?.('');
                            }}
                            isDisabled={isDisabled || value.trim().length === 0}
                            data-testid={"model-settings-editor__clear-button"}
                    >
                        <TimesIcon/>
                    </Button>
                </InputGroup>
            )}
            {!isPassword && (
                <InputGroup>
                    <TextInput
                        value={value}
                        type={"text"}
                        onChange={(value, event) => props.onChange?.(value)}
                        aria-label={props["aria-label"]}
                        placeholder={placeholder}
                        isDisabled={isDisabled}
                        data-testid={"model-settings-editor__input"}
                    />
                    <Button variant="plain"
                            aria-label={t('ClearText')}
                            title={t('ClearText')}
                            onClick={() => {
                                onChange?.('');
                            }}
                            isDisabled={isDisabled || value.trim().length === 0}
                            data-testid={"model-settings-editor__clear-button"}
                    >
                        <TimesIcon/>
                    </Button>
                </InputGroup>
            )}
        </>
    );
}
