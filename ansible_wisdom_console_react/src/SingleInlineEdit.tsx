import {TimesIcon} from "@patternfly/react-icons";
import {Button, InputGroup, TextInput} from "@patternfly/react-core";
import {useTranslation} from "react-i18next";

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
    return (
        <InputGroup>
            <TextInput
                value={props.value}
                type={props.isPassword ? "password" : "text"}
                onChange={(value, event) => props.onChange?.(value)}
                aria-label={props["aria-label"]}
                placeholder={props.placeholder}
                isDisabled={props.isDisabled}
                data-testid={"model-settings-editor__input"}
            />
            <Button variant="plain"
                    aria-label={t('ClearText')}
                    title={t('ClearText')}
                    onClick={() => {
                        props.onChange?.('');
                    }}
                    isDisabled={props.isDisabled || props.value.trim().length === 0}
                    data-testid={"model-settings-editor__clear-button"}
            >
                <TimesIcon/>
            </Button>
        </InputGroup>
    )
        ;
}
