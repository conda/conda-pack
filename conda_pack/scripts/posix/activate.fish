function _activate
    set -l full_path_script_dir (cd (dirname (status -f)); and pwd)
    set -l full_path_env (dirname "$full_path_script_dir")
    set env_name (basename "$full_path_env")

    # If there's already a source env
    if [ -n "$CONDA_PREFIX" ]
        # If the source env differs from this env
        if [ "$CONDA_PREFIX" != "$full_path_env" ]
            deactivate
        else
            return 0  # nothing to do
        end
    end

    export CONDA_PREFIX="$full_path_env"
    set _OLD_PATH "$PATH"
    set PATH "$full_path_env/bin:$PATH"

    functions -c fish_prompt _old_fish_prompt
    function fish_prompt
        # Run the user's prompt first; it might depend on (pipe)status.
        set -l prompt (_old_fish_prompt)

        printf "($env_name) "

        string join -- \n $prompt # handle multi-line prompts
    end

    # Run the activate scripts
    set -l _script_dir "$full_path_env/etc/conda/activate.d"
    if [ -d "$_script_dir" ] && [ -n "(ls -A "$_script_dir")" ]
        set -l _path
        for _path in "$_script_dir"/*.sh
            # Normally these are sourced but given they're not-fish scripts it will
            # error out. Run them anyways for any side effects.
            sh "$_path"
        end
        for _path in "$_script_dir"/*.fish
            . "$_path"
        end
    end
end

function deactivate -d 'Exit conda mode and return to the normal environment.'
    # reset old environment variables
    if test -n "$_OLD_PATH"
        set -gx PATH $_OLD_PATH
        set -e _OLD_PATH
    end

    if functions -q _old_fish_prompt
        # Erase virtualenv's `fish_prompt` and restore the original.
        functions -e fish_prompt
        functions -c _old_fish_prompt fish_prompt
        functions -e _old_fish_prompt
    end

    set -e CONDA_PREFIX
end

_activate
